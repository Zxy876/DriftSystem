"""Mod manifest definitions used by the mod manager."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator


class ModAssets(BaseModel):
    schematics: List[str] = Field(default_factory=list)
    structures: List[str] = Field(default_factory=list)
    scripts: List[str] = Field(default_factory=list)
    textures: List[str] = Field(default_factory=list)


EntryPointValue = Union[str, List[str]]


class ModManifest(BaseModel):
    mod_id: str
    name: Optional[str] = None
    version: str = "0.1.0"
    description: Optional[str] = None
    authors: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    assets: ModAssets = Field(default_factory=ModAssets)
    entry_points: Dict[str, EntryPointValue] = Field(default_factory=dict)
    metadata: Dict[str, str] = Field(default_factory=dict)

    root_path: Optional[Path] = Field(default=None, exclude=True)

    @field_validator("mod_id")
    @classmethod
    def validate_mod_id(cls, value: str) -> str:
        if not value or ":" not in value:
            msg = "mod_id must follow namespace:identifier format"
            raise ValueError(msg)
        return value

    def resource_path(self, relative: str) -> Optional[Path]:
        if not self.root_path:
            return None
        candidate = (self.root_path / relative).resolve()
        if candidate.exists():
            return candidate
        return None

    def command_list(self, key: str) -> List[str]:
        entry = self.entry_points.get(key)
        if isinstance(entry, str):
            command = entry.strip()
            return [command] if command else []
        if isinstance(entry, list):
            return [str(item).strip() for item in entry if str(item).strip()]
        return []

    def build_commands(self) -> List[str]:
        return self.command_list("build")
