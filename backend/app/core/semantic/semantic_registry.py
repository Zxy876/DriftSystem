from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional


BASE_CONTENT_DIR = Path(__file__).resolve().parents[2] / "content"
VANILLA_PATH = BASE_CONTENT_DIR / "scenes" / "semantic_tags.json"
MOD_MAP_PATH = BASE_CONTENT_DIR / "semantic" / "mod_semantic_map.json"


def normalize_semantic_item_id(value: Any) -> str:
    token = str(value or "").strip().lower()
    if not token:
        return ""
    return token.replace("-", "_").replace(" ", "_")


def _normalize_tag(value: Any) -> str:
    token = str(value or "").strip().lower()
    if not token:
        return ""
    return token.replace("-", "_").replace(" ", "_")


def _normalize_tags(raw_values: Any) -> List[str]:
    rows: List[str] = []
    seen = set()

    values: List[Any]
    if isinstance(raw_values, list):
        values = list(raw_values)
    else:
        values = [raw_values]

    for value in values:
        token = _normalize_tag(value)
        if not token or token in seen:
            continue
        seen.add(token)
        rows.append(token)

    return rows


def _read_json(path: Path) -> Any:
    if not path.exists() or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _with_aliases(mapping: Dict[str, List[str]], *, item_id: str, tags: List[str]) -> None:
    if not item_id or not tags:
        return

    if item_id not in mapping:
        mapping[item_id] = list(tags)

    if ":" in item_id:
        suffix = item_id.split(":", 1)[1]
        if suffix and suffix not in mapping:
            mapping[suffix] = list(tags)
    else:
        minecraft_alias = f"minecraft:{item_id}"
        if minecraft_alias not in mapping:
            mapping[minecraft_alias] = list(tags)


class SemanticRegistry:
    def __init__(self) -> None:
        self.vanilla = self._load_map(VANILLA_PATH)
        self.mod = self._load_map(MOD_MAP_PATH)

    @staticmethod
    def _load_map(path: Path) -> Dict[str, List[str]]:
        payload = _read_json(path)
        if not isinstance(payload, dict):
            return {}

        mapping: Dict[str, List[str]] = {}
        for raw_key, raw_value in payload.items():
            item_id = normalize_semantic_item_id(raw_key)
            if not item_id:
                continue
            tags = _normalize_tags(raw_value)
            if not tags:
                continue
            _with_aliases(mapping, item_id=item_id, tags=tags)

        return mapping

    def get_vanilla(self, item_id: str) -> Optional[List[str]]:
        normalized = normalize_semantic_item_id(item_id)
        if not normalized:
            return None
        values = self.vanilla.get(normalized)
        if not isinstance(values, list):
            return None
        return list(values)

    def get_mod(self, item_id: str) -> Optional[List[str]]:
        normalized = normalize_semantic_item_id(item_id)
        if not normalized:
            return None
        values = self.mod.get(normalized)
        if not isinstance(values, list):
            return None
        return list(values)


@lru_cache(maxsize=1)
def get_semantic_registry() -> SemanticRegistry:
    return SemanticRegistry()
