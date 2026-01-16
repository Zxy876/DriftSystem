"""Dynamic resource snapshot builder leveraging installed mods and resource packs."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Set

_RESOURCE_ID_PATTERN = re.compile(r"\b([a-z0-9_.-]+:[a-z0-9_./-]+)\b")


@dataclass
class _IntermediateRecord:
    resource_id: str
    label: str
    category: str
    aliases: Set[str]
    tags: Set[str]
    commands: List[str]
    available: Optional[int] = None

    def to_resource_record(self) -> ResourceRecord:
        from .resource_snapshot import ResourceRecord

        return ResourceRecord(
            resource_id=self.resource_id,
            label=self.label,
            category=self.category,
            aliases=sorted(self.aliases),
            tags=sorted(self.tags),
            available=self.available,
            commands=self.commands[:],
        )


class ResourceSnapshotBuilder:
    """Build a resource snapshot by scanning repo artefacts."""

    def __init__(
        self,
        *,
        backend_root: Path,
        output_path: Path,
        seed_path: Path,
    ) -> None:
        self._backend_root = backend_root
        self._repo_root = backend_root.parent
        self._output_path = output_path
        self._seed_path = seed_path

    def generate(self) -> ResourceSnapshot:
        from .resource_snapshot import ResourceSnapshot

        records = self._collect_records()
        snapshot = ResourceSnapshot(
            resources=sorted(
                (record.to_resource_record() for record in records.values()),
                key=lambda record: record.resource_id,
            ),
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        self._persist(snapshot)
        return snapshot

    # ---------------------------------------------------------------------
    # Collection pipeline
    # ---------------------------------------------------------------------
    def _collect_records(self) -> MutableMapping[str, _IntermediateRecord]:
        registry: MutableMapping[str, _IntermediateRecord] = {}
        # Seed entries ensure we retain curated mappings from earlier phases.
        self._merge_seed_entries(registry)
        lang_labels = self._load_language_labels()
        self._merge_resourcepack_entries(registry, lang_labels)
        self._merge_mod_entries(registry, lang_labels)
        return registry

    def _merge_seed_entries(self, registry: MutableMapping[str, _IntermediateRecord]) -> None:
        if not self._seed_path.exists():
            return
        seed_payload = self._read_json_dict(self._seed_path)
        resources = seed_payload.get("resources") if isinstance(seed_payload, dict) else None
        if not isinstance(resources, Sequence):
            return
        for entry in resources:
            if not isinstance(entry, Mapping):
                continue
            resource_id = str(entry.get("resource_id") or "").strip()
            label = str(entry.get("label") or "").strip()
            if not resource_id or not label:
                continue
            category = str(entry.get("category") or "block")
            aliases = {str(alias).strip().lower() for alias in entry.get("aliases", []) if isinstance(alias, str)}
            tags = {str(tag).strip() for tag in entry.get("tags", []) if isinstance(tag, str)}
            commands = [str(cmd) for cmd in entry.get("commands", []) if isinstance(cmd, str)]
            record = _IntermediateRecord(
                resource_id=resource_id,
                label=label,
                category=category,
                aliases={alias for alias in aliases if alias},
                tags={tag for tag in tags if tag},
                commands=commands,
                available=self._safe_int(entry.get("available")),
            )
            registry[resource_id] = record

    def _merge_resourcepack_entries(
        self,
        registry: MutableMapping[str, _IntermediateRecord],
        lang_labels: Mapping[str, str],
    ) -> None:
        assets_root = self._repo_root / "resourcepack" / "assets"
        if not assets_root.exists():
            return
        for namespace_dir in assets_root.iterdir():
            if not namespace_dir.is_dir():
                continue
            namespace = namespace_dir.name
            # Blockstates and models refer to buildable structures.
            targets = [
                (namespace_dir / "blockstates", "block"),
                (namespace_dir / "models" / "block", "block"),
                (namespace_dir / "models" / "item", "item"),
            ]
            for target_dir, category in targets:
                if not target_dir.exists():
                    continue
                for file in target_dir.glob("*.json"):
                    resource_id = f"{namespace}:{file.stem}"
                    label = lang_labels.get(resource_id, self._humanize(resource_id))
                    aliases = self._default_aliases(resource_id, label)
                    tags = {f"namespace:{namespace}", "source:resourcepack"}
                    self._merge_record(
                        registry,
                        resource_id=resource_id,
                        label=label,
                        category=category,
                        aliases=aliases,
                        tags=tags,
                        commands=[],
                    )

    def _merge_mod_entries(
        self,
        registry: MutableMapping[str, _IntermediateRecord],
        lang_labels: Mapping[str, str],
    ) -> None:
        mods_root = self._repo_root / "mods"
        if not mods_root.exists():
            return
        for mod_json in mods_root.glob("*/mod.json"):
            payload = self._read_json_dict(mod_json)
            if not payload:
                continue
            mod_name = str(payload.get("name") or mod_json.parent.name)
            mod_id = str(payload.get("mod_id") or mod_json.parent.name)
            mod_tags = [str(tag) for tag in payload.get("tags", []) if isinstance(tag, str)]
            command_lists = []
            entry_points = payload.get("entry_points")
            if isinstance(entry_points, Mapping):
                for value in entry_points.values():
                    if isinstance(value, Sequence):
                        command_lists.extend([str(item) for item in value if isinstance(item, str)])
            found_resources: Dict[str, List[str]] = defaultdict(list)
            for command in command_lists:
                for match in _RESOURCE_ID_PATTERN.findall(command):
                    found_resources[match].append(command)
            for resource_id, commands in found_resources.items():
                label = lang_labels.get(resource_id, self._humanize(resource_id))
                aliases = self._default_aliases(resource_id, label)
                aliases.update(self._tokenise(mod_name))
                tags = {f"mod:{mod_id}", "source:mods", *mod_tags}
                self._merge_record(
                    registry,
                    resource_id=resource_id,
                    label=label,
                    category=self._infer_category(resource_id),
                    aliases=aliases,
                    tags=tags,
                    commands=commands,
                )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _merge_record(
        self,
        registry: MutableMapping[str, _IntermediateRecord],
        *,
        resource_id: str,
        label: str,
        category: str,
        aliases: Iterable[str],
        tags: Iterable[str],
        commands: Sequence[str],
    ) -> None:
        normalized_aliases = {alias.strip().lower() for alias in aliases if alias and alias.strip()}
        normalized_tags = {tag.strip() for tag in tags if tag and tag.strip()}
        trimmed_commands = [self._trim_command(cmd) for cmd in commands if cmd and cmd.strip()]
        record = registry.get(resource_id)
        if record is None:
            registry[resource_id] = _IntermediateRecord(
                resource_id=resource_id,
                label=label,
                category=category,
                aliases=normalized_aliases,
                tags=normalized_tags,
                commands=trimmed_commands,
            )
            return
        if label and not record.label:
            record.label = label
        record.category = record.category or category
        record.aliases.update(normalized_aliases)
        record.tags.update(normalized_tags)
        record.commands = self._merge_unique(record.commands, trimmed_commands)

    def _load_language_labels(self) -> Dict[str, str]:
        assets_root = self._repo_root / "resourcepack" / "assets"
        lang_files = []
        for namespace_dir in assets_root.glob("*/lang"):
            for pref in ("zh_cn.json", "en_us.json"):
                candidate = namespace_dir / pref
                if candidate.exists():
                    lang_files.append(candidate)
        labels: Dict[str, str] = {}
        for lang_file in lang_files:
            payload = self._read_json_dict(lang_file)
            if not payload:
                continue
            for key, value in payload.items():
                if not isinstance(key, str) or not isinstance(value, str):
                    continue
                parts = key.split(".")
                if len(parts) < 3:
                    continue
                namespace = parts[1]
                name = ".".join(parts[2:])
                resource_id = f"{namespace}:{name}"
                labels.setdefault(resource_id, value)
        return labels

    @staticmethod
    def _default_aliases(resource_id: str, label: str) -> Set[str]:
        aliases = {label.lower(), ResourceSnapshotBuilder._humanize(resource_id).lower()}
        aliases.add(resource_id.split(":", 1)[-1].replace("_", " "))
        segments = ResourceSnapshotBuilder._tokenise(label)
        aliases.update(segments)
        return {alias for alias in aliases if alias}

    @staticmethod
    def _tokenise(text: str) -> Set[str]:
        tokens = re.sub(r"[^a-z0-9]+", " ", text.lower()).split()
        return {token for token in tokens if token}

    @staticmethod
    def _humanize(resource_id: str) -> str:
        name = resource_id.split(":", 1)[-1]
        return re.sub(r"[_/]+", " ", name).title()

    @staticmethod
    def _infer_category(resource_id: str) -> str:
        if resource_id.startswith("minecraft:"):
            return "block"
        if resource_id.startswith("drift:"):
            return "structure"
        if resource_id.startswith("gm4:"):
            return "structure"
        return "item"

    @staticmethod
    def _trim_command(command: str) -> str:
        return " ".join(command.strip().split())

    @staticmethod
    def _merge_unique(existing: Sequence[str], new_values: Sequence[str]) -> List[str]:
        merged: List[str] = []
        seen: Set[str] = set()
        for value in list(existing) + list(new_values):
            if not value or value in seen:
                continue
            seen.add(value)
            merged.append(value)
        return merged

    @staticmethod
    def _safe_int(value: object) -> Optional[int]:
        try:
            if value is None:
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _read_json_dict(path: Path) -> Dict[str, object]:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return {}
        if not text.strip():
            return {}
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _persist(self, snapshot: ResourceSnapshot) -> None:
        payload = snapshot.to_payload()
        payload["generated_at"] = snapshot.generated_at
        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        self._output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )