"""Runtime loader for Ideal City mods cloned into the workspace."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .manifest import ModManifest


@dataclass
class ModRecord:
    manifest: ModManifest
    manifest_path: Path

    @property
    def mod_id(self) -> str:
        return self.manifest.mod_id

    @property
    def root_path(self) -> Path:
        return self.manifest_path.parent


class ModManager:
    """Discover and serve mods stored under the repository's mods directory."""

    def __init__(self, mods_root: Optional[Path] = None) -> None:
        env_root = os.getenv("IDEAL_CITY_MODS_ROOT")
        if mods_root is not None:
            root = mods_root
        elif env_root:
            root = Path(env_root)
        else:
            root = Path(__file__).resolve().parents[4] / "mods"
        self.mods_root = root
        self._mods: Dict[str, ModRecord] = {}
        self.reload()

    def reload(self) -> None:
        self._mods.clear()
        if not self.mods_root.exists():
            return
        for path in self.mods_root.iterdir():
            if not path.is_dir():
                continue
            manifest_path = path / "mod.json"
            if not manifest_path.exists():
                continue
            try:
                manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            try:
                manifest = ModManifest.model_validate(manifest_data)
            except Exception:
                continue
            manifest.root_path = path
            self._mods[manifest.mod_id] = ModRecord(manifest=manifest, manifest_path=manifest_path)

    def list_mods(self) -> List[ModRecord]:
        return sorted(self._mods.values(), key=lambda record: record.mod_id)

    def get_mod(self, mod_id: str) -> Optional[ModRecord]:
        return self._mods.get(mod_id)

    def resolve_asset(self, mod_id: str, asset_path: str) -> Optional[Path]:
        record = self.get_mod(mod_id)
        if not record:
            return None
        return record.manifest.resource_path(asset_path)

    def has_mod(self, mod_id: str) -> bool:
        return mod_id in self._mods

    def iter_manifests(self) -> Iterable[ModManifest]:
        for record in self.list_mods():
            yield record.manifest

    def build_commands(self, mod_id: str) -> List[str]:
        record = self.get_mod(mod_id)
        if not record:
            return []
        return record.manifest.build_commands()
