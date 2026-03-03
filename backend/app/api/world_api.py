import os
import time
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal
import logging

from app.core.world.engine import WorldEngine
from app.core.story.story_engine import story_engine
from app.core.world.trigger import trigger_engine
from app.core.ai.intent_engine import parse_intent
from app.core.quest.runtime import quest_runtime

router = APIRouter(prefix="/world", tags=["World"])
world_engine = WorldEngine()
logger = logging.getLogger("uvicorn.error")
APPLY_REPORTS_LIMIT = 20
REPORT_STATUS_RANK: Dict[str, int] = {
    "REJECTED": 1,
    "PARTIAL": 2,
    "EXECUTED": 3,
}
apply_reports_by_player: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
fallback_state_by_player: Dict[str, Dict[str, Any]] = defaultdict(dict)


def _now_ms() -> int:
    return int(time.time() * 1000)


def _rank_for_status(status: str) -> int:
    return REPORT_STATUS_RANK.get(status, 0)


def _upsert_apply_report(report: "ApplyReportInput") -> Dict[str, Any]:
    player_reports = apply_reports_by_player[report.player_id]
    build_id = report.build_id
    now_ms = _now_ms()
    incoming_rank = _rank_for_status(report.status)
    existing = player_reports.get(build_id)

    if not existing:
        record = {
            "build_id": build_id,
            "player_id": report.player_id,
            "report_count": 1,
            "first_seen_ms": now_ms,
            "last_seen_ms": now_ms,
            "status_rank": incoming_rank,
            "last_status": report.status,
            "last_failure_code": report.failure_code,
            "last_executed": report.executed,
            "last_failed": report.failed,
            "last_duration_ms": report.duration_ms,
            "last_payload_hash": report.payload_hash,
            "received_at": datetime.now(timezone.utc).isoformat(),
        }
        player_reports[build_id] = record
        return record

    existing["report_count"] = int(existing.get("report_count", 0)) + 1
    existing["last_seen_ms"] = now_ms
    existing["received_at"] = datetime.now(timezone.utc).isoformat()

    current_rank = int(existing.get("status_rank", 0))
    should_overwrite = incoming_rank > current_rank or incoming_rank == current_rank

    if should_overwrite:
        existing["status_rank"] = incoming_rank
        existing["last_status"] = report.status
        existing["last_failure_code"] = report.failure_code
        existing["last_executed"] = report.executed
        existing["last_failed"] = report.failed
        existing["last_duration_ms"] = report.duration_ms
        existing["last_payload_hash"] = report.payload_hash

    return existing


def _recent_reports_for_player(player_id: str) -> list[Dict[str, Any]]:
    reports = list(apply_reports_by_player.get(player_id, {}).values())
    reports.sort(key=lambda item: int(item.get("last_seen_ms", 0)), reverse=True)
    return reports[:APPLY_REPORTS_LIMIT]


def _record_fallback_state(
    *,
    player_id: str,
    fallback_flag: bool,
    reason: str,
    level_id: Optional[str] = None,
    inject_version: Optional[str] = None,
) -> Dict[str, Any]:
    state = {
        "last_fallback_flag": bool(fallback_flag),
        "last_fallback_reason": reason,
        "last_fallback_level_id": level_id,
        "last_fallback_inject_version": inject_version,
        "last_fallback_at": datetime.now(timezone.utc).isoformat(),
    }
    fallback_state_by_player[player_id] = state
    return state

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


class ApplyReportInput(BaseModel):
    build_id: str = Field(min_length=1)
    player_id: str = Field(min_length=1)
    status: Literal["EXECUTED", "REJECTED", "PARTIAL"]
    failure_code: str = Field(min_length=1)
    executed: int = Field(ge=0)
    failed: int = Field(ge=0)
    duration_ms: int = Field(ge=0)
    payload_hash: str = Field(min_length=1)


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
                    text=raw_text,
                    player_id=player_id,
                )
                inject_result = api_story_inject(payload)

                if isinstance(inject_result, dict) and inject_result.get("version") == "plugin_payload_v1":
                    _record_fallback_state(
                        player_id=player_id,
                        fallback_flag=False,
                        reason="payload_v1",
                        level_id=level_id,
                        inject_version="plugin_payload_v1",
                    )
                    return WorldApplyResponse(
                        status="ok",
                        world_state=new_state,
                        story_node={
                            "title": "✨ 世界已创建",
                            "text": f"AI为你生成了新世界：{intent.get('title', '自由创作')}"
                        },
                        world_patch=inject_result,
                    )

                inject_version = inject_result.get("version") if isinstance(inject_result, dict) else None
                fallback_reason = "inject_non_payload_v1"
                _record_fallback_state(
                    player_id=player_id,
                    fallback_flag=True,
                    reason=fallback_reason,
                    level_id=level_id,
                    inject_version=str(inject_version) if inject_version is not None else None,
                )
                logger.warning(
                    "[CREATE_STORY] fell back to legacy world_patch; player_id=%s level_id=%s reason=%s inject_version=%s",
                    player_id,
                    level_id,
                    fallback_reason,
                    inject_version,
                )
                
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
                    ai_response=inject_result.get("world_preview")
                )
            except Exception as e:
                # 创建失败时返回错误信息
                return WorldApplyResponse(
                    status="error",
                    world_state=new_state,
                    story_node={
                        "title": "创建失败", 
                        "text": f"世界生成出错: {str(e)}"
                    }
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
                world_patch=patch
            )

        if t == "GOTO_NEXT_LEVEL":
            next_level = story_engine.get_next_level_id(None, player_id=player_id)
            patch = story_engine.load_level_for_player(player_id, next_level)
            new_state = world_engine.apply_patch(patch)

            return WorldApplyResponse(
                status="ok",
                world_state=new_state,
                story_node={"title": "下一关", "text": f"进入 {next_level}"},
                world_patch=patch
            )

        # ---------- 小地图 ----------
        if t == "SHOW_MINIMAP":
            mm = story_engine.minimap.to_dict(player_id)
            return WorldApplyResponse(
                status="ok",
                world_state=new_state,
                story_node={"title": "小地图", "text": "显示当前世界地图"},
                world_patch={"minimap": mm},
            )

        # ---------- 时间 ----------
        if t == "SET_DAY":
            patch = {"mc": {"time": "day"}}
            new_state = world_engine.apply_patch(patch)
            return WorldApplyResponse(status="ok", world_state=new_state, world_patch=patch)

        if t == "SET_NIGHT":
            patch = {"mc": {"time": "night"}}
            new_state = world_engine.apply_patch(patch)
            return WorldApplyResponse(status="ok", world_state=new_state, world_patch=patch)

        # ---------- 天气 ----------
        if t == "SET_WEATHER":
            w = intent.get("weather", "clear")
            patch = {"mc": {"weather": w}}
            new_state = world_engine.apply_patch(patch)
            return WorldApplyResponse(status="ok", world_state=new_state, world_patch=patch)

        # ---------- 造实体 ----------
        if t == "SPAWN_ENTITY":
            patch = {"mc": {
                "spawn": {
                    "type": intent.get("entity", "villager"),
                    "name": "NPC",
                    "offset": {"dx": 1, "dy": 0, "dz": 1}
                }
            }}
            new_state = world_engine.apply_patch(patch)
            return WorldApplyResponse(status="ok", world_state=new_state, world_patch=patch)

        # ---------- 建筑 ----------
        if t == "BUILD_STRUCTURE":
            patch = {"mc": {"build": intent.get("build")}}
            new_state = world_engine.apply_patch(patch)
            return WorldApplyResponse(status="ok", world_state=new_state, world_patch=patch)

    # ============================================================
    # ⭐ 剧情推进（只要说话一定触发）
    # ============================================================
    if say_text:
        option, node, patch = story_engine.advance(player_id, new_state, act)

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
            world_patch=patch
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
            trigger={"id": tp.id, "level_id": tp.level_id}
        )

    # ============================================================
    # 默认（比如走路，没有剧情）
    # ============================================================
    return WorldApplyResponse(
        status="ok",
        world_state=new_state
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

    recent_reports = _recent_reports_for_player(player_id)
    last_report = recent_reports[0] if recent_reports else None
    fallback_state = fallback_state_by_player.get(player_id, {})

    snapshot = quest_runtime.get_debug_snapshot(player_id)
    if not snapshot:
        return {
            "status": "error",
            "msg": "No active task state for player.",
            "recent_apply_reports": recent_reports,
            "last_apply_report": last_report,
            "last_fallback_flag": fallback_state.get("last_fallback_flag", False),
            "last_fallback_reason": fallback_state.get("last_fallback_reason", "none"),
            "last_fallback_level_id": fallback_state.get("last_fallback_level_id"),
            "last_fallback_inject_version": fallback_state.get("last_fallback_inject_version"),
            "last_fallback_at": fallback_state.get("last_fallback_at"),
        }

    payload: Dict[str, Any] = {"status": "ok"}
    payload.update(snapshot)
    payload["recent_apply_reports"] = recent_reports
    payload["last_apply_report"] = last_report
    payload["last_fallback_flag"] = fallback_state.get("last_fallback_flag", False)
    payload["last_fallback_reason"] = fallback_state.get("last_fallback_reason", "none")
    payload["last_fallback_level_id"] = fallback_state.get("last_fallback_level_id")
    payload["last_fallback_inject_version"] = fallback_state.get("last_fallback_inject_version")
    payload["last_fallback_at"] = fallback_state.get("last_fallback_at")
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


@router.post("/apply/report")
def apply_report(report: ApplyReportInput):
    merged = _upsert_apply_report(report)

    logger.info(
        "world_apply_report",
        extra={
            "player_id": report.player_id,
            "build_id": report.build_id,
            "status": report.status,
            "failure_code": report.failure_code,
            "executed": report.executed,
            "failed": report.failed,
            "duration_ms": report.duration_ms,
        },
    )

    return {
        "status": "ok",
        "accepted": True,
        "player_id": report.player_id,
        "build_id": report.build_id,
        "report_count": merged.get("report_count", 1),
        "last_status": merged.get("last_status"),
        "status_rank": merged.get("status_rank"),
    }
