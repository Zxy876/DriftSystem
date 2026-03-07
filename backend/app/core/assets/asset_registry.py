from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def _normalize_token(value: Any) -> str:
    token = str(value or "").strip().lower()
    return token.replace(" ", "_")


def _normalize_tokens(values: Iterable[Any]) -> List[str]:
    normalized: List[str] = []
    seen = set()
    for raw in values:
        token = _normalize_token(raw)
        if not token or token in seen:
            continue
        seen.add(token)
        normalized.append(token)
    return normalized


class AssetRegistry:
    def __init__(self, file_path: Path) -> None:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        self.version = str(payload.get("version") or "").strip() or "unknown"
        raw_assets = payload.get("assets")
        if not isinstance(raw_assets, dict):
            raw_assets = {}

        self.assets: Dict[str, Dict[str, Any]] = {}
        for raw_id, raw_data in raw_assets.items():
            if not isinstance(raw_data, dict):
                continue
            asset_id = _normalize_token(raw_id)
            if not asset_id:
                continue
            normalized_asset = dict(raw_data)
            normalized_asset["id"] = asset_id
            normalized_asset["type"] = _normalize_token(raw_data.get("type") or "")
            normalized_asset["source"] = _normalize_token(raw_data.get("source") or "unknown")
            normalized_asset["semantic_tags"] = _normalize_tokens(raw_data.get("semantic_tags") or [])
            self.assets[asset_id] = normalized_asset

    def get(self, asset_id: str) -> Optional[Dict[str, Any]]:
        normalized_id = _normalize_token(asset_id)
        if not normalized_id:
            return None
        asset = self.assets.get(normalized_id)
        if asset is None:
            return None
        return dict(asset)

    def list_assets(self) -> List[str]:
        return sorted(self.assets.keys())

    def filter_by_semantics(self, tags: Iterable[str]) -> List[str]:
        normalized_tags = _normalize_tokens(tags)
        if not normalized_tags:
            return self.list_assets()
        selected: List[str] = []
        for asset_id, asset in self.assets.items():
            asset_tags = set(asset.get("semantic_tags") or [])
            if all(tag in asset_tags for tag in normalized_tags):
                selected.append(asset_id)
        return sorted(selected)

    def filter_by_any_semantics(self, tags: Iterable[str]) -> List[str]:
        normalized_tags = _normalize_tokens(tags)
        if not normalized_tags:
            return self.list_assets()
        selected: List[str] = []
        tag_set = set(normalized_tags)
        for asset_id, asset in self.assets.items():
            asset_tags = set(asset.get("semantic_tags") or [])
            if asset_tags.intersection(tag_set):
                selected.append(asset_id)
        return sorted(selected)

    def sources_for_assets(self, asset_ids: Iterable[str]) -> List[str]:
        sources: List[str] = []
        seen = set()
        for raw_id in asset_ids:
            asset = self.get(str(raw_id))
            if not isinstance(asset, dict):
                continue
            source = _normalize_token(asset.get("source") or "unknown")
            if not source or source in seen:
                continue
            seen.add(source)
            sources.append(source)
        return sources
