import os

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Iterable, List
import logging

from app.core.world.engine import WorldEngine
from app.core.story.story_engine import story_engine
from app.core.world.trigger import trigger_engine
from app.core.ai.intent_engine import parse_intent
from app.core.quest.runtime import quest_runtime
from app.core.intent_creation import CreationIntentDecision
from app.services import creation_workflow
BLOCK_KEYWORDS = {"方块", "方塊", "blocks", "block"}


def _summarize_commands(commands: Iterable[str]) -> List[Dict[str, Any]]:
    summaries: List[Dict[str, Any]] = []
    for raw in commands:
        command = (raw or "").strip()
        if not command:
            continue
        parts = command.split()
        if not parts:
            continue
        opcode = parts[0].lower()
        if opcode == "setblock" and len(parts) >= 5:
            summaries.append(
                {
                    "type": "setblock",
                    "coords": parts[1:4],
                    "block": parts[4],
                }
            )
        elif opcode == "fill" and len(parts) >= 8:
            summaries.append(
                {
                    "type": "fill",
                    "from": parts[1:4],
                    "to": parts[4:7],
                    "block": parts[7],
                }
            )
        else:
            summaries.append({"type": opcode, "command": command})
    return summaries


def _looks_like_block_request(message: Optional[str], decision: Optional[CreationIntentDecision]) -> bool:
    if not message:
        return False

    text = message.strip()
    if any(keyword in text for keyword in BLOCK_KEYWORDS):
        return True

    lower = text.lower()
    if "minecraft:" in lower and lower.endswith("_block"):
        return True

    if decision is None:
        return False

    materials: Iterable[str] = decision.slots.get("materials", []) if isinstance(decision.slots, dict) else []
    for material in materials:
        token = str(material).strip().lower()
        if not token:
            continue
        if token.endswith("块") or token.endswith("方塊") or "block" in token or token.endswith("_block"):
            return True
        if token.startswith("minecraft:") and any(part in token for part in ("block", "brick", "glass", "plank", "stone")):
            return True
    return False

router = APIRouter(prefix="/world", tags=["World"])
world_engine = WorldEngine()
logger = logging.getLogger("uvicorn.error")

# ============================================================
# MODELS
# ============================================================
class MoveAction(BaseModel):
    x: float
    y: float
    z: float
    speed: float = 0.0
    moving: bool = False


class WorldAction(BaseModel):
    move: Optional[MoveAction] = None
    say: Optional[str] = None


class ApplyInput(BaseModel):
    action: WorldAction
    player_id: Optional[str] = "default"


class WorldApplyResponse(BaseModel):
    status: str
    world_state: Dict[str, Any]
    ai_option: Optional[str] = None              # ⭐ 已修复：必须是 str
    story_node: Optional[Dict[str, Any]] = None
    world_patch: Optional[Dict[str, Any]] = None
    trigger: Optional[Dict[str, Any]] = None
    creation_result: Optional[Dict[str, Any]] = None


class EnterStoryRequest(BaseModel):
    player_id: str
    level_id: Optional[str] = None


class EndStoryRequest(BaseModel):
    player_id: str
    level_id: Optional[str] = None


class RuleTriggerEvent(BaseModel):
    player_id: str
    event_type: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


# ============================================================
# APPLY API — v3（最终版）
# ============================================================
@router.post("/apply", response_model=WorldApplyResponse)
def apply_action(inp: ApplyInput):

    player_id = inp.player_id
    act = inp.action.dict(exclude_none=True)

    # 1) 世界物理更新
    new_state = world_engine.apply(act)
    vars_ = new_state.get("variables") or {}
    x = vars_.get("x", 0)
    y = vars_.get("y", 0)
    z = vars_.get("z", 0)

    # 2) 文本 → 意图解析
    say_text = act.get("say")
    intent_result = parse_intent(player_id, say_text, new_state, story_engine) if say_text else None
    
    # 提取第一个 intent（如果有多个，这里只处理第一个）
    intent = None
    if intent_result and "intents" in intent_result and len(intent_result["intents"]) > 0:
        intent = intent_result["intents"][0]

    creation_result: Optional[Dict[str, Any]] = None
    creation_report = None
    creation_world_patch: Optional[Dict[str, Any]] = None
    block_story_world_patch = False
    creation_decision: Optional[CreationIntentDecision] = None
    primary_intent_type = intent.get("type") if isinstance(intent, dict) else None
    redirected_to_block = False

    if say_text:
        creation_decision = creation_workflow.classify_message(say_text)
        logger.info(
            "creation_intent_classified",
            extra={
                "player_id": player_id,
                "primary_intent": primary_intent_type,
                "creation": creation_decision.model_dump(),
            },
        )

        looks_like_block = _looks_like_block_request(say_text, creation_decision)

        if looks_like_block:
            if intent and primary_intent_type in {"SPAWN_ENTITY", "SAY_ONLY", "UNKNOWN", None}:
                intent["type"] = "CREATE_BLOCK"
                intent.setdefault("raw_text", say_text)
                primary_intent_type = "CREATE_BLOCK"
                redirected_to_block = True
            elif intent is None:
                intent = {"type": "CREATE_BLOCK", "raw_text": say_text}
                primary_intent_type = "CREATE_BLOCK"
                intent_result = intent_result or {"status": "ok", "intents": []}
                intent_result.setdefault("intents", []).insert(0, intent)
                redirected_to_block = True

        if intent and primary_intent_type == "SPAWN_ENTITY" and creation_decision.is_creation:
            if looks_like_block:
                intent["type"] = "CREATE_BLOCK"
                primary_intent_type = "CREATE_BLOCK"
                redirected_to_block = True

        should_auto_execute = creation_decision.is_creation and primary_intent_type in (
            None,
            "SAY_ONLY",
            "BUILD_STRUCTURE",
            "CREATE_BLOCK",
            "CREATE_BUILD",
        )

        if should_auto_execute:
            try:
                plan_result = creation_workflow.generate_plan(creation_decision, message=say_text)
                report = creation_workflow.auto_execute_plan(plan_result.plan)
                creation_report = report
                plan_payload = plan_result.plan.to_payload()
                plan_payload["snapshot_generated_at"] = plan_result.snapshot_generated_at
                auto_enabled = creation_workflow.auto_execute_enabled()
                creation_result = {
                    "status": "ok" if auto_enabled else "validated",
                    "auto_execute": auto_enabled,
                    "decision": creation_decision.model_dump(),
                    "plan": plan_payload,
                    "report": report.to_payload(),
                }
                creation_world_patch = creation_workflow.world_patch_from_report(report)
            except Exception as exc:  # pragma: no cover - defensive path
                logger.exception(
                    "creation_auto_execute_failed",
                    extra={"player_id": player_id, "message": say_text},
                )
                creation_result = {
                    "status": "error",
                    "error": str(exc),
                    "decision": creation_decision.model_dump(),
                }

    if (
        creation_result
        and primary_intent_type in {"CREATE_BLOCK", "CREATE_BUILD"}
        and str(creation_result.get("status")) in {"validated", "ok"}
    ):
        block_story_world_patch = True
        if creation_world_patch is None and creation_report is not None:
            creation_world_patch = creation_workflow.world_patch_from_report(creation_report)

    # ============================================================
    # ⭐ 白名单世界指令（不走剧情）
    # ============================================================
    if intent:
        t = intent["type"]

        # ---------- 创建故事关卡（AI生成完整世界） ----------
        if t == "CREATE_STORY":
            import hashlib
            import time
            from app.api.story_api import InjectPayload, api_story_inject
            
            # 生成唯一level_id
            raw_text = intent.get("raw_text", "story")
            level_id = f"flagship_story_{hashlib.md5(f'{raw_text}{time.time()}'.encode()).hexdigest()[:8]}"
            
            # 调用story_api创建关卡（AI会生成完整世界）
            try:
                payload = InjectPayload(
                    level_id=level_id,
                    title=intent.get("title", "自由创作"),
                    text=raw_text
                )
                inject_result = api_story_inject(payload)
                
                # 立即加载生成的关卡
                patch = story_engine.load_level_for_player(player_id, level_id)
                new_state = world_engine.apply_patch(patch)
                
                return WorldApplyResponse(
                    status="ok",
                    world_state=new_state,
                    story_node={
                        "title": "✨ 世界已创建", 
                        "text": f"AI为你生成了新世界：{intent.get('title', '自由创作')}"
                    },
                    world_patch=patch,
                    ai_response=inject_result.get("world_preview"),
                    creation_result=creation_result,
                )
            except Exception as e:
                # 创建失败时返回错误信息
                return WorldApplyResponse(
                    status="error",
                    world_state=new_state,
                    story_node={
                        "title": "创建失败", 
                        "text": f"世界生成出错: {str(e)}"
                    },
                    creation_result=creation_result,
                )

        # ---------- 跳关 ----------
        if t == "GOTO_LEVEL":
            level = intent.get("level_id")
            canonical = story_engine.graph.canonicalize_level_id(level) if level else None
            level = canonical or level
            patch = story_engine.load_level_for_player(player_id, level)
            new_state = world_engine.apply_patch(patch)

            return WorldApplyResponse(
                status="ok",
                world_state=new_state,
                story_node={"title": "跳转关卡", "text": f"进入 {level}"},
                world_patch=patch,
                creation_result=creation_result,
            )

        if t == "GOTO_NEXT_LEVEL":
            next_level = story_engine.get_next_level_id(None, player_id=player_id)
            patch = story_engine.load_level_for_player(player_id, next_level)
            new_state = world_engine.apply_patch(patch)

            return WorldApplyResponse(
                status="ok",
                world_state=new_state,
                story_node={"title": "下一关", "text": f"进入 {next_level}"},
                world_patch=patch,
                creation_result=creation_result,
            )

        # ---------- 小地图 ----------
        if t == "SHOW_MINIMAP":
            mm = story_engine.minimap.to_dict(player_id)
            return WorldApplyResponse(
                status="ok",
                world_state=new_state,
                story_node={"title": "小地图", "text": "显示当前世界地图"},
                world_patch={"minimap": mm},
                creation_result=creation_result,
            )

        # ---------- 时间 ----------
        if t == "SET_DAY":
            patch = {"mc": {"time": "day"}}
            new_state = world_engine.apply_patch(patch)
            return WorldApplyResponse(status="ok", world_state=new_state, world_patch=patch, creation_result=creation_result)

        if t == "SET_NIGHT":
            patch = {"mc": {"time": "night"}}
            new_state = world_engine.apply_patch(patch)
            return WorldApplyResponse(status="ok", world_state=new_state, world_patch=patch, creation_result=creation_result)

        # ---------- 天气 ----------
        if t == "SET_WEATHER":
            w = intent.get("weather", "clear")
            patch = {"mc": {"weather": w}}
            new_state = world_engine.apply_patch(patch)
            return WorldApplyResponse(status="ok", world_state=new_state, world_patch=patch, creation_result=creation_result)

        # ---------- 造实体 ----------
        if t == "SPAWN_ENTITY" and not redirected_to_block:
            patch = {"mc": {
                "spawn": {
                    "type": intent.get("entity", "villager"),
                    "name": "NPC",
                    "offset": {"dx": 1, "dy": 0, "dz": 1}
                }
            }}
            new_state = world_engine.apply_patch(patch)
            return WorldApplyResponse(status="ok", world_state=new_state, world_patch=patch, creation_result=creation_result)

        # ---------- 建筑 ----------
        if t == "BUILD_STRUCTURE":
            patch = {"mc": {"build": intent.get("build")}}
            new_state = world_engine.apply_patch(patch)
            return WorldApplyResponse(status="ok", world_state=new_state, world_patch=patch, creation_result=creation_result)

    # ============================================================
    # ⭐ 剧情推进（只要说话一定触发）
    # ============================================================
    if say_text:
        option, node, patch = story_engine.advance(player_id, new_state, act)
        final_patch = creation_world_patch if block_story_world_patch else patch

        if block_story_world_patch and creation_world_patch:
            commands = creation_world_patch.get("mc", {}).get("commands", []) if isinstance(creation_world_patch, dict) else []
            metadata = creation_world_patch.get("metadata", {}) if isinstance(creation_world_patch, dict) else {}
            coordinates = metadata.get("coordinates") if isinstance(metadata, dict) else None
            position_hint = None
            if isinstance(metadata, dict):
                for key in ("position_hint", "origin", "source"):
                    if metadata.get(key):
                        position_hint = metadata.get(key)
                        break
            logger.info(
                "creation_world_patch_override",
                extra={
                    "intent_type": primary_intent_type or "UNKNOWN",
                    "patch_id": metadata.get("patch_id") if isinstance(metadata, dict) else None,
                    "commands": _summarize_commands(commands),
                    "coordinates": coordinates,
                    "position_hint": position_hint,
                },
            )

        # 🛡️ 确保 ai_option 始终为字符串，兼容 DeepSeek 返回数组/对象
        option_value = None
        if isinstance(option, str) or option is None:
            option_value = option
        elif isinstance(option, (list, tuple)):
            if option:
                option_value = str(option[0])
        elif isinstance(option, (dict, int, float, bool)):
            option_value = str(option)
        else:
            option_value = None

        return WorldApplyResponse(
            status="ok",
            world_state=new_state,
            ai_option=option_value,
            story_node=node,
            world_patch=final_patch,
            creation_result=creation_result,
        )

    # ============================================================
    # ⭐ 触发器（走路触发 level）
    # ============================================================
    tp = trigger_engine.check(player_id, x, y, z)

    if tp and tp.action == "load_level":
        patch = story_engine.load_level_for_player(player_id, tp.level_id)
        new_state = world_engine.apply_patch(patch)

        return WorldApplyResponse(
            status="ok",
            world_state=new_state,
            story_node={"title": "世界触发点", "text": f"成功加载 {tp.level_id}"},
            world_patch=patch,
            trigger={"id": tp.id, "level_id": tp.level_id},
            creation_result=creation_result,
        )

    # ============================================================
    # 默认（比如走路，没有剧情）
    # ============================================================
    return WorldApplyResponse(
        status="ok",
        world_state=new_state,
        creation_result=creation_result,
    )


@router.get("/state/{player_id}")
def world_state(player_id: str):
    """Return a combined snapshot of the simulated world and story engine."""

    story_snapshot = story_engine.get_public_state(player_id)
    state = world_engine.get_state() or {}
    world_snapshot = {
        "variables": dict(state.get("variables", {})),
        "entities": dict(state.get("entities", {})),
    }

    return {
        "status": "ok",
        "player_id": player_id,
        "world": world_snapshot,
        "story": story_snapshot,
    }


# ============================================================
# Phase 1.5 skeleton endpoints
# ============================================================


@router.post("/story/enter")
def story_enter(request: EnterStoryRequest):
    target_level = request.level_id or story_engine.get_next_level_id(None, player_id=request.player_id)
    patch = None
    if target_level:
        patch = story_engine.load_level_for_player(request.player_id, target_level)
    logger.info("story_enter", extra={"player_id": request.player_id, "level_id": target_level})
    return {
        "status": "ok",
        "level_id": target_level,
        "world_patch": patch,
    }


@router.post("/story/start")
def story_start(request: EnterStoryRequest):
    preferred_level = request.level_id
    if not preferred_level:
        preferred_level = (
            story_engine.graph.get_start_level()
            or story_engine.DEFAULT_ENTRY_LEVEL
        )

    patch = None
    if preferred_level:
        patch = story_engine.load_level_for_player(request.player_id, preferred_level)

    logger.info(
        "story_start",
        extra={"player_id": request.player_id, "level_id": preferred_level},
    )

    return {
        "status": "ok",
        "level_id": preferred_level,
        "world_patch": patch,
    }


@router.post("/story/end")
def story_end(request: EndStoryRequest):
    player_state = story_engine.players.get(request.player_id, {})
    level = player_state.get("level")
    cleanup_patch = None
    if level:
        cleanup_patch = story_engine.exit_level_with_cleanup(request.player_id, level)
    else:
        quest_runtime.exit_level(request.player_id)
    logger.info("story_end", extra={"player_id": request.player_id, "level_id": getattr(level, "level_id", None)})
    return {
        "status": "ok",
        "world_patch": cleanup_patch,
    }


@router.post("/story/rule-event")
def story_rule_event(event: RuleTriggerEvent):
    response = quest_runtime.handle_rule_trigger(event.player_id, {
        "event_type": event.event_type,
        "payload": event.payload,
    })
    logger.debug(
        "story_rule_event",
        extra={"player_id": event.player_id, "event_type": event.event_type},
    )
    result = {"status": "ok", "result": response}
    if isinstance(response, dict):
        story_engine.apply_quest_updates(event.player_id, response)
        if response.get("world_patch"):
            result["world_patch"] = response["world_patch"]
        if response.get("nodes"):
            result["nodes"] = response["nodes"]
        if response.get("completed_tasks"):
            result["completed_tasks"] = response["completed_tasks"]
        if response.get("milestones"):
            result["milestones"] = response["milestones"]
        if response.get("commands"):
            result["commands"] = response["commands"]
        if response.get("active_tasks"):
            result["active_tasks"] = response["active_tasks"]
        if response.get("memory_flags"):
            result["memory_flags"] = response["memory_flags"]
        for key in ("task_titles", "milestone_names", "remaining_total", "active_count", "milestone_count"):
            if key in response:
                result[key] = response[key]
    return result


@router.get("/story/{player_id}/memory")
def story_memory(player_id: str):
    flags = story_engine.get_player_memory(player_id)
    return {
        "status": "ok",
        "player_id": player_id,
        "flags": flags,
    }


@router.get("/story/{player_id}/emotional-weather")
def story_emotional_weather(player_id: str):
    summary = story_engine.get_emotional_profile(player_id)
    return {
        "status": "ok",
        "player_id": player_id,
        "emotional_state": summary or None,
    }


@router.get("/story/{player_id}/recommendations")
def story_recommendations(player_id: str, current_level: Optional[str] = None, limit: int = 3):
    recs = story_engine.get_level_recommendations(player_id, current_level_id=current_level, limit=limit)
    return {
        "status": "ok",
        "recommendations": recs,
    }


@router.get("/story/{player_id}/debug/tasks")
def story_debug_tasks(player_id: str, request: Request, token: Optional[str] = None):
    expected_token = os.environ.get("DRIFT_TASK_DEBUG_TOKEN")
    if expected_token:
        provided = token or request.headers.get("X-Debug-Token")
        if provided != expected_token:
            raise HTTPException(status_code=403, detail="Task debug access denied.")

    snapshot = quest_runtime.get_debug_snapshot(player_id)
    if not snapshot:
        return {"status": "error", "msg": "No active task state for player."}

    payload: Dict[str, Any] = {"status": "ok"}
    payload.update(snapshot)
    return payload


@router.get("/story/{player_id}/quest-log")
def story_quest_log(player_id: str):
    snapshot = quest_runtime.get_active_tasks_snapshot(player_id)
    response: Dict[str, Any] = {
        "status": "ok",
        "active_tasks": snapshot,
    }
    if snapshot:
        for key in ("task_titles", "milestone_names", "remaining_total", "active_count", "milestone_count"):
            if key in snapshot:
                response[key] = snapshot[key]
    return response
