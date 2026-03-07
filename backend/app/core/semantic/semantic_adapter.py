from __future__ import annotations

from .semantic_registry import get_semantic_registry, normalize_semantic_item_id
from .semantic_types import SemanticResult


def resolve_semantics(item_id: str) -> SemanticResult:
    normalized_item = normalize_semantic_item_id(item_id)
    if not normalized_item:
        return {
            "item_id": "",
            "semantic_tags": ["generic"],
            "source": "fallback",
            "adapter_hit": False,
        }

    registry = get_semantic_registry()

    vanilla_tags = registry.get_vanilla(normalized_item)
    if vanilla_tags:
        return {
            "item_id": normalized_item,
            "semantic_tags": list(vanilla_tags),
            "source": "vanilla_registry",
            "adapter_hit": True,
        }

    mod_tags = registry.get_mod(normalized_item)
    if mod_tags:
        return {
            "item_id": normalized_item,
            "semantic_tags": list(mod_tags),
            "source": "mod_map",
            "adapter_hit": True,
        }

    return {
        "item_id": normalized_item,
        "semantic_tags": [normalized_item],
        "source": "fallback",
        "adapter_hit": False,
    }
