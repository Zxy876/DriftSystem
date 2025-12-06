# backend/app/core/story/story_loader.py
import os, json
from dataclasses import dataclass
from typing import Dict, Any, Optional, List

# backend/app/core/story/story_loader.py
# __file__ = backend/app/core/story/story_loader.py
# 往上三层到 backend/
BACKEND_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
DATA_DIR = os.path.join(BACKEND_DIR, "data", "heart_levels")


@dataclass
class Level:
    level_id: str
    title: str
    text: List[str]
    tags: List[str]
    mood: Dict[str, Any]
    choices: List[Dict[str, Any]]
    meta: Dict[str, Any]
    npcs: List[Dict[str, Any]]
    bootstrap_patch: Dict[str, Any]
    tree: Optional[Dict[str, Any]] = None


def _list_json_files() -> List[str]:
    if not os.path.exists(DATA_DIR):
        return []
    return sorted([
        f for f in os.listdir(DATA_DIR)
        if f.endswith(".json") and not f.startswith("_")
    ])


def list_levels() -> List[Dict[str, Any]]:
    """
    返回 heart_levels 目录下的关卡元数据列表
    """
    levels = []
    for fn in _list_json_files():
        path = os.path.join(DATA_DIR, fn)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            levels.append({
                "id": data.get("id", fn.replace(".json", "")),
                "title": data.get("title", ""),
                "file": fn,
                "tags": data.get("tags", []),
                "chapter": (data.get("meta") or {}).get("chapter"),
                "word_count": (data.get("meta") or {}).get("word_count"),
            })
        except Exception as e:
            levels.append({
                "id": fn.replace(".json", ""),
                "title": f"[BROKEN] {fn}",
                "file": fn,
                "error": str(e)
            })
    return levels


def load_level(level_id: str) -> Level:
    """
    读取单个 level_xx.json
    """
    # 允许用户传 level_1 或 level_1.json
    filename = level_id if level_id.endswith(".json") else f"{level_id}.json"
    path = os.path.join(DATA_DIR, filename)

    if not os.path.exists(path):
        raise FileNotFoundError(f"Level file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 兼容 text 是 list / 或 string
    raw_text = data.get("text", [])
    if isinstance(raw_text, str):
        text_list = [raw_text]
    else:
        text_list = list(raw_text)

    # npcs / world_patch / tree 可能不存在
    npcs = data.get("npcs", []) or []
    # 优先使用 world_patch (增强配置)，fallback 到 bootstrap_patch
    world_patch = data.get("world_patch") or data.get("bootstrap_patch", {
        "variables": {},
        "mc": {"tell": f"关卡 {data.get('title','')} 已加载。"}
    })
    tree = data.get("tree")

    return Level(
        level_id=data.get("id", level_id),
        title=data.get("title", level_id),
        text=text_list,
        tags=data.get("tags", []),
        mood=data.get("mood", {"base":"calm","intensity":0.5}),
        choices=data.get("choices", []),
        meta=data.get("meta", {}),
        npcs=npcs,
        bootstrap_patch=world_patch,  # 使用world_patch作为bootstrap_patch
        tree=tree
    )


def build_level_prompt(level: Level) -> str:
    """
    把心悦文集文章转成 AI 的关卡系统提示词。
    """
    npc_lines = []
    for n in level.npcs:
        npc_lines.append(
            f"- NPC: {n.get('name','未知')} "
            f"(type={n.get('type','villager')}, role={n.get('role','人物')}) "
            f"personality={n.get('personality','')}"
        )
    npc_block = "\n".join(npc_lines) if npc_lines else "- 本关暂无固定NPC"

    text_block = "\n".join(level.text)

    prompt = f"""
【关卡ID】{level.level_id}
【关卡标题】{level.title}

【心悦文集原文（世界观与剧情核）】
{text_block}

【固定NPC（文章主人公/配角的灵魂）】
{npc_block}

【规则】
- 你必须让剧情与原文情绪、人物关系一致，但允许玩家干预与分支。
- 玩家可选择“接受/拒绝/折中”你的剧情推进；你要给出清晰的 option 与 node。
- 如果本关 meta/choices 给了固定出口，也可以用它当作“主线终点”参考。
""".strip()

    return prompt