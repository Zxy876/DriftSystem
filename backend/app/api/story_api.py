# backend/app/api/story_api.py

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
import os
import json
import re

from app.core.story.story_loader import (
    list_levels,
    load_level,
    DATA_DIR,          # ⭐ 使用 story_loader 的同一个目录
)
from app.core.story.story_engine import story_engine
from app.core.scene.scene_orchestrator_v1 import compose_scene_and_structure
from app.core.scene.scene_orchestrator_v2 import compose_scene_and_structure_v2
from app.core.executor.plugin_payload_v1 import build_plugin_payload_v1
from app.core.executor.plugin_payload_v2 import build_plugin_payload_v2_with_trace, PayloadV2BuildError

router = APIRouter(prefix="/story")


class PayloadV1BuildError(Exception):
    def __init__(self, failure_code: str, debug_payload: dict | None = None):
        super().__init__(failure_code)
        self.failure_code = failure_code
        self.debug_payload = debug_payload or {}


class PayloadV2BuildErrorWrapper(Exception):
    def __init__(self, failure_code: str, debug_payload: dict | None = None):
        super().__init__(failure_code)
        self.failure_code = failure_code
        self.debug_payload = debug_payload or {}


def _normalize_injected_level_id(raw_level_id: str) -> str:
    """Ensure injected level ids follow the flagship_* convention."""

    sanitized = (raw_level_id or "").strip()
    if not sanitized:
        return "flagship_custom"

    if sanitized.endswith(".json"):
        sanitized = sanitized[:-5]

    lowered = sanitized.lower()

    if lowered.startswith("flagship_"):
        return sanitized

    if lowered.startswith("level_"):
        suffix = sanitized.split("_", 1)[1]
        if suffix:
            try:
                return f"flagship_{int(suffix):02d}"
            except ValueError:
                return f"flagship_{suffix}"

    if lowered.startswith("custom_") or lowered.startswith("story_"):
        return f"flagship_{sanitized}"

    if lowered.isdigit():
        return f"flagship_{int(lowered):02d}"

    return sanitized

# ============================================================
# ✔ Pydantic 模型（用于 JSON 注入）
# ============================================================
class InjectPayload(BaseModel):
    level_id: str     # test_inject
    title: str        # 测试剧情
    text: str         # 单段剧情文本（自动转成 list）
    player_id: Optional[str] = "default"
    anchor: Optional[str] = None


SCENE_ANCHOR_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
SCENE_ANCHOR_IDS = ("home", "npc_zone", "interaction_zone", "memory_scene")


def _normalize_scene_anchor_id(raw_anchor: str | None) -> str | None:
    if raw_anchor is None:
        return None
    if not isinstance(raw_anchor, str):
        return None

    normalized = raw_anchor.strip().lower()
    if not normalized:
        return None
    if not SCENE_ANCHOR_ID_PATTERN.fullmatch(normalized):
        return None

    return normalized


def _scene_anchor_from_text(text: str) -> str:
    lowered = (text or "").lower()

    memory_keywords = ("回忆", "记忆", "往事", "梦境", "memory", "flashback")
    npc_keywords = ("npc", "守卫", "村民", "商人", "villager", "zombie", "skeleton")
    interaction_keywords = ("互动", "交互", "对话", "任务", "解谜", "interaction")

    if any(keyword in lowered for keyword in memory_keywords):
        return "memory_scene"
    if any(keyword in lowered for keyword in npc_keywords):
        return "npc_zone"
    if any(keyword in lowered for keyword in interaction_keywords):
        return "interaction_zone"
    return "home"


def _origin_from_scene_anchor_env(anchor_id: str, fallback: dict) -> dict:
    env_prefix = f"DRIFT_SCENE_ANCHOR_{anchor_id.upper()}"
    return {
        "base_x": int(os.environ.get(f"{env_prefix}_X", str(fallback["base_x"]))),
        "base_y": int(os.environ.get(f"{env_prefix}_Y", str(fallback["base_y"]))),
        "base_z": int(os.environ.get(f"{env_prefix}_Z", str(fallback["base_z"]))),
        "anchor_mode": fallback.get("anchor_mode", "fixed"),
    }


def _scene_anchors_from_env(base_origin: dict) -> dict:
    home = {
        "base_x": int(base_origin["base_x"]),
        "base_y": int(base_origin["base_y"]),
        "base_z": int(base_origin["base_z"]),
        "anchor_mode": str(base_origin.get("anchor_mode") or "fixed"),
    }

    npc_zone_default = {
        "base_x": home["base_x"] + 24,
        "base_y": home["base_y"],
        "base_z": home["base_z"],
        "anchor_mode": home["anchor_mode"],
    }
    interaction_zone_default = {
        "base_x": home["base_x"],
        "base_y": home["base_y"],
        "base_z": home["base_z"] + 24,
        "anchor_mode": home["anchor_mode"],
    }
    memory_scene_default = {
        "base_x": home["base_x"] - 32,
        "base_y": home["base_y"] + 6,
        "base_z": home["base_z"] - 32,
        "anchor_mode": home["anchor_mode"],
    }

    return {
        "home": _origin_from_scene_anchor_env("home", home),
        "npc_zone": _origin_from_scene_anchor_env("npc_zone", npc_zone_default),
        "interaction_zone": _origin_from_scene_anchor_env("interaction_zone", interaction_zone_default),
        "memory_scene": _origin_from_scene_anchor_env("memory_scene", memory_scene_default),
    }


def _resolve_scene_anchor(*, text: str, requested_anchor: str | None) -> str:
    normalized_requested = _normalize_scene_anchor_id(requested_anchor)
    if normalized_requested in SCENE_ANCHOR_IDS:
        return normalized_requested

    env_anchor = _normalize_scene_anchor_id(os.environ.get("DRIFT_SCENE_ANCHOR"))
    if env_anchor in SCENE_ANCHOR_IDS:
        return env_anchor

    inferred = _scene_anchor_from_text(text)
    if inferred in SCENE_ANCHOR_IDS:
        return inferred
    return "home"


def _build_level_document(level_id: str, title: str, text: str, bootstrap_patch: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": level_id,
        "title": title,
        "text": [text],
        "tags": [],
        "mood": {"base": "calm", "intensity": 0.5},
        "choices": [],
        "meta": {},
        "npcs": [],
        "bootstrap_patch": bootstrap_patch,
        "world_patch": bootstrap_patch,
        "tree": None,
    }


def _as_bool_env(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _fixed_anchor_from_env() -> dict:
    return {
        "base_x": int(os.environ.get("DRIFT_FIXED_ANCHOR_X", "0")),
        "base_y": int(os.environ.get("DRIFT_FIXED_ANCHOR_Y", "64")),
        "base_z": int(os.environ.get("DRIFT_FIXED_ANCHOR_Z", "0")),
        "anchor_mode": "fixed",
    }


def _extract_debug_payload(compose_result: dict) -> dict:
    mapping_result = compose_result.get("mapping_result") or {}
    decision_trace = compose_result.get("decision_trace") or mapping_result.get("trace") or {}
    rule_version = decision_trace.get("rule_version") if isinstance(decision_trace, dict) else None
    engine_version = decision_trace.get("engine_version") if isinstance(decision_trace, dict) else None
    return {
        "mapping_status": mapping_result.get("status", "UNAVAILABLE"),
        "mapping_failure_code": mapping_result.get("failure_code", "UNAVAILABLE"),
        "degrade_reason": mapping_result.get("degrade_reason"),
        "lost_semantics": mapping_result.get("lost_semantics") or [],
        "rule_version": rule_version,
        "engine_version": engine_version,
        "decision_trace": decision_trace,
        "compose_path": compose_result.get("compose_path", "unknown"),
    }


def _build_payload_v1_for_inject(*, player_id: str, text: str) -> tuple[dict, dict]:
    use_v2_mapper = _as_bool_env("DRIFT_USE_V2_MAPPER", default=False)
    strict_mode = _as_bool_env("DRIFT_V2_STRICT_MODE", default=False)

    if use_v2_mapper:
        compose_result = compose_scene_and_structure_v2(text, strict_mode=strict_mode)
    else:
        compose_result = compose_scene_and_structure(text)

    if compose_result.get("status") != "SUCCESS":
        debug_payload = _extract_debug_payload(compose_result) if _as_bool_env("DRIFT_DEBUG_TRACE", default=False) else {}
        raise PayloadV1BuildError(compose_result.get("failure_code", "COMPOSE_FAILED"), debug_payload)

    payload_v1 = build_plugin_payload_v1(
        compose_result,
        player_id=player_id,
        origin=_fixed_anchor_from_env(),
    )

    debug_payload: dict = {}
    if _as_bool_env("DRIFT_DEBUG_TRACE", default=False):
        debug_payload = _extract_debug_payload(compose_result)

    return payload_v1, debug_payload


def _build_payload_v2_for_inject(*, player_id: str, text: str, anchor: str | None = None) -> tuple[dict, dict]:
    strict_mode = _as_bool_env("DRIFT_V2_STRICT_MODE", default=False)

    compose_result = compose_scene_and_structure_v2(text, strict_mode=strict_mode)
    if compose_result.get("status") != "SUCCESS":
        debug_payload = _extract_debug_payload(compose_result) if _as_bool_env("DRIFT_DEBUG_TRACE", default=False) else {}
        raise PayloadV2BuildErrorWrapper(compose_result.get("failure_code", "COMPOSE_FAILED"), debug_payload)

    base_origin = _fixed_anchor_from_env()
    scene_anchors = _scene_anchors_from_env(base_origin)
    selected_anchor = _resolve_scene_anchor(text=text, requested_anchor=anchor)

    try:
        payload_v2, payload_trace = build_plugin_payload_v2_with_trace(
            compose_result,
            player_id=player_id,
            origin=base_origin,
            strict_mode=strict_mode,
            anchor=selected_anchor,
            anchors=scene_anchors,
        )
    except PayloadV2BuildError as exc:
        debug_payload = {}
        if _as_bool_env("DRIFT_DEBUG_TRACE", default=False):
            debug_payload = _extract_debug_payload(compose_result)
            debug_payload.update({
                "payload_v2_failure_code": exc.failure_code,
                "payload_v2_trace": exc.trace or {},
            })
        raise PayloadV2BuildErrorWrapper(exc.failure_code, debug_payload) from exc

    debug_payload: dict = {}
    if _as_bool_env("DRIFT_DEBUG_TRACE", default=False):
        debug_payload = _extract_debug_payload(compose_result)
        debug_payload["payload_v2_trace"] = payload_trace
        debug_payload["scene_anchor"] = selected_anchor

    return payload_v2, debug_payload


# ============================================================
# ✔ 获取所有关卡
# ============================================================
@router.get("/levels")
def api_story_levels():
    return {"status": "ok", "levels": list_levels()}


# ============================================================
# ✔ 获取关卡详情
# ============================================================
@router.get("/level/{level_id}")
def api_story_level(level_id: str):
    try:
        lv = load_level(level_id)
        return {"status": "ok", "level": lv.__dict__}
    except FileNotFoundError:
        return {"status": "error", "msg": f"Level {level_id} not found"}


# ============================================================
# ✔ 加载关卡（Minecraft 进入剧情）
# ============================================================
@router.post("/load/{player_id}/{level_id}")
def api_story_load(player_id: str, level_id: str):
    try:
        patch = story_engine.load_level_for_player(player_id, level_id)
        return {"status": "ok", "msg": f"{level_id} loaded", "bootstrap_patch": patch}
    except FileNotFoundError:
        return {"status": "error", "msg": f"Level {level_id} not found"}


# ============================================================
# ✔ 推进剧情
# ============================================================
@router.post("/advance/{player_id}")
def api_story_advance(player_id: str, payload: Dict[str, Any]):
    world_state = payload.get("world_state", {}) or {}
    action = payload.get("action", {}) or {}

    option, node, patch = story_engine.advance(player_id, world_state, action)
    return {
        "status": "ok",
        "option": option,
        "node": node,
        "world_patch": patch
    }


# ============================================================
# ✔ 获取玩家当前 Story 状态
# ============================================================
@router.get("/state/{player_id}")
def api_story_state(player_id: str):
    return {"status": "ok", "state": story_engine.get_public_state(player_id)}


# ============================================================
# ⭐ NEW：创建新的剧情关卡（以 JSON Body 注入）
# ============================================================
@router.post("/inject")
def api_story_inject(payload: InjectPayload):
    """
    JSON Body 示例：
    {
        "level_id": "test_inject",
        "title": "测试剧情",
        "text": "这是自动注入的剧情节点"
    }
    """
    LEVEL_DIR = DATA_DIR                         # ⭐ 与 story_loader 使用相同目录
    os.makedirs(LEVEL_DIR, exist_ok=True)

    level_id = _normalize_injected_level_id(payload.level_id)

    file_path = os.path.join(LEVEL_DIR, f"{level_id}.json")

    if os.path.exists(file_path):
        raise HTTPException(
            status_code=400,
            detail=f"Level {level_id} already exists"
        )

    use_payload_v1 = _as_bool_env("DRIFT_USE_PAYLOAD_V1", default=False)
    use_payload_v2 = _as_bool_env("DRIFT_USE_PAYLOAD_V2", default=False)

    if use_payload_v2:
        try:
            player_id = (payload.player_id or "default").strip() or "default"
            payload_v2, debug_payload = _build_payload_v2_for_inject(
                player_id=player_id,
                text=payload.text,
                anchor=payload.anchor,
            )

            level_doc = _build_level_document(
                level_id=level_id,
                title=payload.title,
                text=payload.text,
                bootstrap_patch=payload_v2,
            )

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(level_doc, f, ensure_ascii=False, indent=2)

            result = dict(payload_v2)
            result.update({
                "status": "ok",
                "msg": f"Level {level_id} created with payload_v2",
                "level_id": level_id,
                "file": file_path,
            })
            if debug_payload:
                result.update(debug_payload)
            return result
        except PayloadV2BuildErrorWrapper as exc:
            response = {
                "detail": f"payload_v2_build_failed: {exc.failure_code}",
            }
            if _as_bool_env("DRIFT_DEBUG_TRACE", default=False) and exc.debug_payload:
                response.update(exc.debug_payload)
            return JSONResponse(status_code=422, content=response)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"payload_v2_build_failed: {exc}") from exc

    if use_payload_v1:
        try:
            player_id = (payload.player_id or "default").strip() or "default"
            payload_v1, debug_payload = _build_payload_v1_for_inject(player_id=player_id, text=payload.text)

            level_doc = _build_level_document(
                level_id=level_id,
                title=payload.title,
                text=payload.text,
                bootstrap_patch=payload_v1,
            )

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(level_doc, f, ensure_ascii=False, indent=2)

            result = dict(payload_v1)
            result.update({
                "status": "ok",
                "msg": f"Level {level_id} created with payload_v1",
                "level_id": level_id,
                "file": file_path,
            })
            if debug_payload:
                result.update(debug_payload)
            return result
        except PayloadV1BuildError as exc:
            response = {
                "detail": f"payload_v1_build_failed: {exc.failure_code}",
            }
            if _as_bool_env("DRIFT_DEBUG_TRACE", default=False) and exc.debug_payload:
                response.update(exc.debug_payload)
            return JSONResponse(status_code=422, content=response)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"payload_v1_build_failed: {exc}") from exc

    # ⭐ 使用AI生成完整的世界内容（NPC、环境、建筑等）
    from app.core.ai.deepseek_agent import call_deepseek
    
    ai_prompt = f"""
基于用户的故事描述生成一个完整的Minecraft世界场景。
用户描述：{payload.text}

要求：
1. 生成spawn点（玩家出生位置）
2. 生成至少1-3个NPC（类型从villager/zombie/skeleton/cow/pig选择）
3. 生成环境建筑（使用简单方块如stone/oak_planks/glass等）
4. 设置天气和时间（如晴天/白天，或雨天/夜晚营造氛围）

返回JSON格式：
{{
  "spawn": {{"x": 0, "y": 70, "z": 0}},
  "npcs": [
    {{"type": "villager", "name": "商人", "x": 5, "y": 70, "z": 0, "dialog": "欢迎光临！"}},
    {{"type": "cow", "name": "奶牛", "x": -3, "y": 70, "z": 2}}
  ],
  "blocks": [
    {{"type": "stone", "x": 0, "y": 69, "z": 0}},
    {{"type": "oak_planks", "x": 1, "y": 70, "z": 1}}
  ],
  "time": "day",
  "weather": "clear"
}}
"""
    
    try:
        ai_result = call_deepseek(
            context={"type": "world_generation", "story": payload.text},
            messages=[{"role": "user", "content": ai_prompt}],
            temperature=0.8
        )
        
        # 解析AI返回的世界数据
        world_data = json.loads(ai_result.get("response", "{}"))
        
        # 构造bootstrap_patch包含AI生成的完整世界
        bootstrap_patch = {
            "variables": {
                "story_world_generated": True,
                "story_title": payload.title
            },
            "mc": {
                "tell": f"§6{payload.title}§r\n{payload.text}",
                "spawn": world_data.get("spawn", {"x": 0, "y": 70, "z": 0}),
                "time": world_data.get("time", "day"),
                "weather": world_data.get("weather", "clear")
            }
        }
        
        # 添加NPC生成指令
        npcs_data = world_data.get("npcs", [])
        if npcs_data:
            bootstrap_patch["mc"]["spawns"] = [
                {
                    "type": npc.get("type", "villager"),
                    "name": npc.get("name", "NPC"),
                    "x": npc.get("x", 0),
                    "y": npc.get("y", 70),
                    "z": npc.get("z", 0),
                    "dialog": npc.get("dialog", "")
                }
                for npc in npcs_data
            ]
        
        # 添加建筑方块（简化处理）
        blocks_data = world_data.get("blocks", [])
        if blocks_data:
            bootstrap_patch["mc"]["blocks"] = blocks_data[:50]  # 限制数量避免卡顿
            
    except Exception as e:
        # AI调用失败时回退到基础版本
        print(f"AI world generation failed: {e}")
        bootstrap_patch = {
            "variables": {},
            "mc": {
                "tell": f"§6{payload.title}§r\n{payload.text}",
                "spawn": {"x": 0, "y": 70, "z": 0}
            }
        }

    data = _build_level_document(
        level_id=level_id,
        title=payload.title,
        text=payload.text,
        bootstrap_patch=bootstrap_patch,
    )

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return {
        "status": "ok",
        "msg": f"Level {level_id} created with AI-generated world",
        "file": file_path,
        "world_preview": bootstrap_patch.get("mc", {})
    }