# backend/app/api/story_api.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import os
import json
import re
import hashlib

from app.core.story.story_loader import (
    list_levels,
    load_level,
    DATA_DIR,          # ⭐ 使用 story_loader 的同一个目录
)
from app.core.story.story_engine import story_engine
from app.routers.scene import realize_scene, _resolve_domain_binding

router = APIRouter(prefix="/story")


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
    execute_confirm: bool = False


def _extract_json_object(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)

    text = str(raw or "").strip()
    if not text:
        return {}

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        try:
            parsed = json.loads(fenced.group(1))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    return {}


def _to_minecraft_block(material: Any) -> str:
    token = str(material or "stone").strip().lower()
    if not token:
        return "minecraft:stone"
    if token.startswith("minecraft:"):
        return token
    return f"minecraft:{token}"


def _to_setblock_command(block_spec: Dict[str, Any]) -> Optional[str]:
    if not isinstance(block_spec, dict):
        return None
    block = _to_minecraft_block(block_spec.get("type") or block_spec.get("block"))
    try:
        x = int(block_spec.get("x", 0))
        y = int(block_spec.get("y", 70))
        z = int(block_spec.get("z", 0))
    except (TypeError, ValueError):
        return None
    return f"setblock {x} {y} {z} {block}"


def _derive_memory_scene_fallback(*, player_id: str, title: str, text: str) -> Dict[str, Any]:
    seed = hashlib.sha256(f"{player_id}|{text}".encode("utf-8")).hexdigest()
    variant = int(seed[:2], 16) % 3

    variants = [
        {
            "material": "spruce_planks",
            "shape": "house",
            "weather": "clear",
            "time": "sunset",
            "npc": "爷爷",
            "pet": "wolf",
        },
        {
            "material": "stone_bricks",
            "shape": "wall",
            "weather": "rain",
            "time": "night",
            "npc": "爷爷",
            "pet": "cat",
        },
        {
            "material": "oak_planks",
            "shape": "platform",
            "weather": "clear",
            "time": "day",
            "npc": "爷爷",
            "pet": "villager",
        },
    ]

    profile = variants[variant]
    lowered = text.lower()
    if any(token in text for token in ("雨", "下雨")):
        profile["weather"] = "rain"
    if any(token in text for token in ("夜", "黑夜", "夜晚")):
        profile["time"] = "night"
    if "白天" in text:
        profile["time"] = "day"
    if "爷爷" not in text and "grandpa" not in lowered:
        profile["npc"] = "回忆引导者"

    anchor_x = (variant - 1) * 4
    anchor_z = 6

    return {
        "tell": f"§6{title}§r\n{text}",
        "title": {
            "main": f"§6{title}",
            "sub": "回忆场景已生成，和爷爷聊聊吧。",
            "fade_in": 10,
            "stay": 60,
            "fade_out": 20,
        },
        "actionbar": "§e输入你的下一句回忆，AI会继续回应。",
        "spawn": {"x": 0, "y": 70, "z": 0},
        "time": profile["time"],
        "weather": profile["weather"],
        "build": {
            "shape": profile["shape"],
            "material": profile["material"],
            "size": 5,
            "offset": {"dx": 0, "dy": 0, "dz": 6},
        },
        "commands": [
            f"fill {anchor_x-2} 69 {anchor_z-2} {anchor_x+2} 69 {anchor_z+2} minecraft:{profile['material']}",
            f"setblock {anchor_x} 70 {anchor_z} minecraft:campfire",
            f"setblock {anchor_x+1} 70 {anchor_z} minecraft:lantern",
            f"setblock {anchor_x-1} 70 {anchor_z} minecraft:lantern",
        ],
        "spawn_multi": [
            {
                "type": "villager",
                "name": profile["npc"],
                "dx": 2,
                "dy": 0,
                "dz": 5,
                "dialog": "我记得那天的风，也记得你。",
            },
            {
                "type": profile["pet"],
                "name": "旧时回声",
                "dx": -2,
                "dy": 0,
                "dz": 4,
            },
        ],
        "particle": {
            "type": "END_ROD",
            "count": 48,
            "radius": 1.6,
        },
        "sound": {
            "type": "BLOCK_NOTE_BLOCK_BELL",
            "volume": 0.8,
            "pitch": 1.0,
        },
    }


def _build_mc_patch(world_data: Dict[str, Any], *, title: str, text: str, player_id: str) -> Dict[str, Any]:
    mc: Dict[str, Any] = {
        "tell": f"§6{title}§r\n{text}",
        "spawn": world_data.get("spawn", {"x": 0, "y": 70, "z": 0}),
        "time": world_data.get("time", "day"),
        "weather": world_data.get("weather", "clear"),
    }

    npcs_data = world_data.get("npcs", [])
    if isinstance(npcs_data, list) and npcs_data:
        mc["spawn_multi"] = [
            {
                "type": str(npc.get("type") or "villager"),
                "name": str(npc.get("name") or "NPC"),
                "x": npc.get("x", 0),
                "y": npc.get("y", 70),
                "z": npc.get("z", 0),
                "dialog": str(npc.get("dialog") or ""),
            }
            for npc in npcs_data
            if isinstance(npc, dict)
        ]

    blocks_data = world_data.get("blocks", [])
    if isinstance(blocks_data, list) and blocks_data:
        commands = [
            cmd
            for cmd in (_to_setblock_command(item) for item in blocks_data[:50])
            if isinstance(cmd, str) and cmd
        ]
        if commands:
            mc["commands"] = commands

    fallback = _derive_memory_scene_fallback(player_id=player_id, title=title, text=text)

    has_scene_geometry = bool(mc.get("commands") or mc.get("build") or mc.get("build_multi"))
    if not has_scene_geometry:
        for key in ("build", "commands"):
            mc.setdefault(key, fallback.get(key))

    if not mc.get("spawn_multi"):
        mc["spawn_multi"] = fallback.get("spawn_multi", [])

    for key in ("title", "actionbar", "particle", "sound"):
        mc.setdefault(key, fallback.get(key))

    return mc


def _build_default_scene(level_id: str, player_id: str) -> Dict[str, Any]:
    scene_id = f"scene_{level_id}"
    mode = "personal"
    domain = "P_AUTO"
    anchor = {"x": 1000, "y": 64, "z": 0}

    try:
        resolved_domain, domain_center, _ = _resolve_domain_binding(mode, player_id, None)
        if isinstance(resolved_domain, str) and resolved_domain.strip():
            domain = resolved_domain.strip().upper()
        if isinstance(domain_center, dict):
            anchor = {
                "x": int(domain_center.get("x", 1000)),
                "y": int(domain_center.get("y", 64)),
                "z": int(domain_center.get("z", 0)),
            }
    except Exception:
        pass

    return {
        "scene_id": scene_id,
        "player_id": player_id,
        "mode": mode,
        "domain": domain,
        "anchor": anchor,
        "assets": [
            {
                "resource_id": "drift:path_axis_1x1x15",
                "anchor": dict(anchor),
            }
        ],
    }


def _realize_scene_from_level(scene_block: Dict[str, Any], *, execute_confirm: bool) -> Dict[str, Any]:
    request_payload = dict(scene_block)
    if execute_confirm:
        request_payload["execute"] = True
    else:
        request_payload["execution_mode"] = "dry_run"

    response = realize_scene(request_payload)
    return response.model_dump() if hasattr(response, "model_dump") else dict(response)


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

    player_id = (payload.player_id or "default").strip() or "default"

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
        
        # 解析AI返回的世界数据（容错：支持 code fence / 脏文本）
        world_data = _extract_json_object(ai_result.get("response", "{}"))
        
        # 构造bootstrap_patch包含AI生成的完整世界
        bootstrap_patch = {
            "variables": {
                "story_world_generated": True,
                "story_title": payload.title,
            },
            "mc": _build_mc_patch(
                world_data,
                title=payload.title,
                text=payload.text,
                player_id=player_id,
            ),
        }
            
    except Exception as e:
        # AI调用失败时回退到基础版本
        print(f"AI world generation failed: {e}")
        bootstrap_patch = {
            "variables": {
                "story_world_generated": False,
                "ai_generation_error": str(e),
            },
            "mc": _build_mc_patch(
                {},
                title=payload.title,
                text=payload.text,
                player_id=player_id,
            ),
        }

    # ⭐ 生成兼容 Level 类的结构（全部字段完整）
    scene_block = _build_default_scene(level_id, player_id)

    data = {
        "id": level_id,
        "title": payload.title,
        "text": [payload.text],                 # ⭐ 必须为 list[str]
        "tags": [],
        "mood": {"base": "calm", "intensity": 0.5},
        "choices": [],
        "meta": {},
        "npcs": [],
        "bootstrap_patch": bootstrap_patch,
        "scene": scene_block,
        "tree": None
    }

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    scene_status = _realize_scene_from_level(scene_block, execute_confirm=payload.execute_confirm)

    return {
        "status": "ok",
        "level_id": level_id,
        "msg": f"Level {level_id} created with AI-generated world",
        "file": file_path,
        "world_preview": bootstrap_patch.get("mc", {}),
        "scene_status": scene_status,
        "scene_request": {
            "scene_id": scene_block.get("scene_id"),
            "player_id": scene_block.get("player_id"),
            "mode": scene_block.get("mode"),
            "domain": scene_block.get("domain"),
            "execution_mode": "execute" if payload.execute_confirm else "dry_run",
        },
    }