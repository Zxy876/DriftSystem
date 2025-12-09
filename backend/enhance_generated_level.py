"""Utilities for synthesizing flagship-format levels from natural language prompts."""

from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

__all__ = ["generate_flagship_level"]


def _slugify(text: str, max_words: int = 4) -> str:
    tokens = re.findall(r"[\w\-]+", text.lower())
    if not tokens:
        return "vision"
    selected = tokens[:max_words]
    slug = "_".join(selected)
    return slug[:48] or "vision"


def _derive_title(description: str, explicit_title: Optional[str] = None) -> str:
    if explicit_title:
        return explicit_title.strip()[:80]
    trimmed = description.strip()
    if len(trimmed) <= 18:
        return f"玩家创作 · {trimmed}"
    return f"玩家创作 · {trimmed[:18]}…"


def _derive_tags(description: str, extra_tags: Optional[List[str]] = None) -> List[str]:
    tags: List[str] = ["user", "generated", "flagship"]
    if extra_tags:
        for tag in extra_tags:
            token = str(tag).strip().lower()
            if token and token not in tags:
                tags.append(token)
    mood_tokens = re.findall(r"月亮|夜|雨|雪|桥|花|海|山|梦|记忆", description)
    mapping = {
        "月亮": "moon",
        "夜": "night",
        "雨": "rain",
        "雪": "snow",
        "桥": "bridge",
        "花": "flower",
        "海": "sea",
        "山": "mountain",
        "梦": "dream",
        "记忆": "memory",
    }
    for tok in mood_tokens:
        mapped = mapping.get(tok)
        if mapped and mapped not in tags:
            tags.append(mapped)
    return tags


def generate_flagship_level(
    description: str,
    *,
    title: Optional[str] = None,
    extra_tags: Optional[List[str]] = None,
) -> Tuple[str, Dict[str, object]]:
    """Return a `(level_id, level_json)` tuple for the given description."""

    cleaned = (description or "").strip()
    if len(cleaned) < 12:
        raise ValueError("描述需要至少 12 个字符，以便生成有效的剧情线索。")

    slug = _slugify(cleaned)
    epoch_ms = int(time.time() * 1000)
    level_id = f"flagship_user_{epoch_ms}"
    derived_title = _derive_title(cleaned, explicit_title=title)
    tags = _derive_tags(cleaned, extra_tags)
    now = datetime.utcnow().isoformat() + "Z"

    narrative_text = [
        f"生成时间：{now}",
        cleaned,
    ]

    storyline_theme = f"user_created_{slug.split('_', 1)[0]}"
    emotional_vector = "player_authored"

    beats = [
        {
            "id": "user_intro",
            "trigger": "on_enter",
            "cinematic": "user_generated_entry",
            "rule_refs": ["user_intro"],
            "world_patch": {
                "mc": {
                    "tell": "✨ 这是玩家亲手绘制的场景，故事刚刚开始。",
                    "music": {"record": "otherside"},
                    "particle": {"type": "glow", "count": 18},
                }
            },
            "choices": [
                {
                    "id": "embrace_scene",
                    "text": "向前一步，拥抱玩家叙事。",
                    "rule_event": "user_choice_embrace",
                    "tags": ["embrace"],
                },
                {
                    "id": "observe_scene",
                    "text": "先观察这幅画面。",
                    "rule_event": "user_choice_observe",
                    "tags": ["observe"],
                },
            ],
        },
        {
            "id": "user_question",
            "trigger": "rule_event:user_choice_embrace",
            "rule_refs": ["user_forward"],
            "memory_set": ["user_memory_embrace"],
            "world_patch": {
                "mc": {
                    "tell": "💫 玩家世界回应了你的靠近。",
                    "particle": {"type": "happy_villager", "count": 16},
                }
            },
        },
        {
            "id": "user_linger",
            "trigger": "rule_event:user_choice_observe",
            "rule_refs": ["user_reflect"],
            "memory_set": ["user_memory_observe"],
            "world_patch": {
                "mc": {
                    "tell": "🌙 你在场景边缘徘徊，情绪在空气中缓慢流动。",
                    "particle": {"type": "dripping_water", "count": 22},
                }
            },
        },
        {
            "id": "user_outro",
            "trigger": "story:continue",
            "rule_refs": [],
            "next_level": None,
            "world_patch": {
                "mc": {
                    "tell": "✨ 玩家叙事完成本章，新的选择正在酝酿。",
                    "weather": "CLEAR",
                }
            },
        },
    ]

    scene = {
        "world": "KunmingLakeStory",
        "teleport": {"x": 4.5, "y": 70, "z": -3.5, "yaw": 180, "pitch": 0},
        "environment": {"weather": "CLEAR", "time": "SUNSET"},
        "structures": ["structures/generated/player_canvas.nbt"],
        "npc_skins": [
            {"id": "玩家影像", "skin": "skins/player_memory.png"},
        ],
    }

    world_patch = {
        "mc": {
            "_scene": {
                "level_id": level_id,
                "title": derived_title,
                "scene_world": "KunmingLakeStory",
                "featured_npc": "玩家影像",
            },
            "tell": cleaned[:120],
            "music": {"record": "otherside"},
            "particle": {"type": "portal", "count": 30},
        },
        "variables": {
            "theme": storyline_theme,
            "arc_position": "user_created",
            "generated_at": now,
        },
    }

    continuity = {
        "previous": "flagship_12",
        "next": None,
        "emotional_vector": emotional_vector,
        "arc_step": 0,
        "origin": "user_generated",
    }

    level_payload: Dict[str, object] = {
        "id": level_id,
        "title": derived_title,
        "tags": tags,
        "meta": {
            "chapter": None,
            "word_count": len(cleaned),
            "source": "player",
            "created_at": now,
        },
        "storyline_theme": storyline_theme,
        "continuity": continuity,
        "narrative": {
            "text": narrative_text,
            "beats": beats,
        },
        "scene": scene,
        "world_patch": world_patch,
        "rules": {
            "listeners": [
                {"id": "user_intro", "on": "user_intro"},
                {"id": "user_forward", "on": "user_forward"},
                {"id": "user_reflect", "on": "user_reflect"},
            ]
        },
        "tasks": [
            {
                "id": "user_generated_walk",
                "type": "story",
                "title": "体验玩家创作的情绪轨迹",
                "conditions": [],
                "milestones": ["embrace", "observe"],
                "rewards": ["memory_fragment_user"],
            }
        ],
        "exit": {
            "phrase_aliases": ["离开玩家创作", "退出玩家章节", "return hub"],
            "return_spawn": "KunmingLakeHub",
            "teleport": {"x": 128.5, "y": 72, "z": -16.5, "yaw": 180, "pitch": 0},
        },
    }

    return level_id, level_payload
