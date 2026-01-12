"""Story template catalog loader shared between quest runtime and story manager."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

try:  # pragma: no cover - import guard
    import yaml
except ImportError as exc:  # pragma: no cover - defensive
    yaml = None  # type: ignore[assignment]


_LIST_FIELDS: set[str] = {
    "goals",
    "logic_outline",
    "resources",
    "community_requirements",
    "success_criteria",
    "world_constraints",
    "risk_register",
    "risk_notes",
    "notes",
}


def _normalise_list(values: Iterable[Any]) -> List[str]:
    result: List[str] = []
    seen: set[str] = set()
    for item in values:
        if item is None:
            continue
        text = str(item).strip()
        if not text:
            continue
        if text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _default_catalog_data() -> Dict[str, Any]:
    return {
        "version": 1,
        "templates": [
            {
                "template_id": "logic_quick_start",
                "milestone_id": "logic_from_npc",
                "source": "npc",
                "expected_patch": {
                    "logic_outline": [
                        "目标：在熄灯区入口搭建安全的气球展台，引导访客。",
                        "执行：现场布置与社区验证两步完成部署。",
                    ],
                },
                "coverage_tags": ["logic_outline"],
            },
            {
                "template_id": "constraint_night_quiet",
                "milestone_id": "constraints_research",
                "source": "research",
                "expected_patch": {
                    "world_constraints": [
                        "夜间能源供应有限，需控制照明用量。",
                        "夜间噪音需控制在社区委员会批准范围内。",
                    ],
                },
                "coverage_tags": ["world_constraints"],
            },
            {
                "template_id": "resource_basic",
                "milestone_id": "resources_supplied",
                "source": "npc",
                "expected_patch": {
                    "resources": [
                        "木材与防雨布 - 社区工坊",
                        "照明设备 - 夜间供电站",
                    ],
                },
                "coverage_tags": ["resource_ledger"],
            },
            {
                "template_id": "risk_safety",
                "milestone_id": "risk_noted",
                "source": "npc",
                "expected_patch": {
                    "risk_register": ["风险: 夜间噪音扰民 / 安装隔音帘"],
                },
                "coverage_tags": ["risk_register"],
            },
            {
                "template_id": "success_night_showcase",
                "milestone_id": "success_defined",
                "source": "npc",
                "expected_patch": {
                    "success_criteria": ["居民按周排班使用，夜间事故为零。"],
                },
                "coverage_tags": ["success_criteria"],
            },
        ],
    }


@dataclass
class TemplateEntry:
    template_id: str
    milestone_id: str
    expected_patch: Dict[str, List[str]] = field(default_factory=dict)
    coverage_tags: List[str] = field(default_factory=list)
    source: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MilestoneSpec:
    milestone_id: str
    templates: List[str] = field(default_factory=list)
    default_source: Optional[str] = None
    expected_patch: Dict[str, List[str]] = field(default_factory=dict)
    coverage_tags: List[str] = field(default_factory=list)


@dataclass
class TemplateCatalog:
    version: int
    templates: Dict[str, TemplateEntry]
    milestones: Dict[str, MilestoneSpec]


def _candidate_paths() -> List[Path]:
    candidates: List[Path] = []
    override = os.getenv("STORY_TEMPLATE_MAP_PATH")
    if override:
        candidates.append(Path(override))
    data_root = os.getenv("IDEAL_CITY_DATA_ROOT")
    if data_root:
        candidates.append(Path(data_root) / "story_templates" / "template_task_map.yaml")
    backend_root = Path(__file__).resolve().parents[3]
    candidates.append(backend_root / "data" / "ideal_city" / "story_templates" / "template_task_map.yaml")
    repo_root = Path(__file__).resolve().parents[4]
    candidates.append(repo_root / "system" / "mc_plugin" / "src" / "main" / "resources" / "story_templates" / "template_task_map.yaml")
    return candidates


def _load_yaml(path: Path) -> Dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML is required to load story template mappings.")
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise exc
    data = yaml.safe_load(text)  # type: ignore[no-untyped-call]
    if not isinstance(data, dict):
        raise ValueError("template_task_map.yaml must contain a mapping at the top level")
    return data


def _merge_expected_patch(base: Dict[str, List[str]], additions: Mapping[str, Any]) -> Dict[str, List[str]]:
    merged = {field: list(values) for field, values in base.items()}
    for field, raw_values in additions.items():
        if field not in _LIST_FIELDS:
            continue
        if isinstance(raw_values, Mapping):
            continue
        if not isinstance(raw_values, Iterable) or isinstance(raw_values, (str, bytes)):
            continue
        normalized = _normalise_list(raw_values)
        if not normalized:
            continue
        existing = merged.setdefault(field, [])
        for value in normalized:
            if value not in existing:
                existing.append(value)
    return merged


@lru_cache(maxsize=1)
def get_template_catalog() -> TemplateCatalog:
    """Load and cache the shared story template mapping."""

    raw: Optional[Dict[str, Any]] = None
    for candidate in _candidate_paths():
        if not candidate.exists():
            continue
        try:
            raw = _load_yaml(candidate)
        except RuntimeError:
            raw = _default_catalog_data()
        except Exception:
            continue
        if raw is not None:
            break
    if raw is None:
        raw = _default_catalog_data()

    version = int(raw.get("version") or 1)
    entries = raw.get("templates") or []
    if not isinstance(entries, list):
        raise ValueError("template_task_map.yaml expects 'templates' to be a list")

    template_map: Dict[str, TemplateEntry] = {}
    milestone_map: Dict[str, MilestoneSpec] = {}

    for item in entries:
        if not isinstance(item, Mapping):
            continue
        template_id = str(item.get("template_id") or "").strip()
        milestone_id = str(item.get("milestone_id") or "").strip()
        if not template_id or not milestone_id:
            continue
        source_value = str(item.get("source") or "").strip() or None
        expected_patch = item.get("expected_patch") or {}
        coverage_tags = item.get("coverage_tags") or []

        normalized_patch: Dict[str, List[str]] = {}
        if isinstance(expected_patch, Mapping):
            normalized_patch = _merge_expected_patch({}, expected_patch)

        normalized_tags = _normalise_list(coverage_tags) if isinstance(coverage_tags, Iterable) else []

        metadata = {
            key: item.get(key)
            for key in ("narrative_task", "npc_id", "npc_name", "trigger_event", "notes")
            if item.get(key) is not None
        }

        template_map[template_id] = TemplateEntry(
            template_id=template_id,
            milestone_id=milestone_id,
            expected_patch=normalized_patch,
            coverage_tags=normalized_tags,
            source=source_value,
            metadata=metadata,
        )

        spec = milestone_map.setdefault(milestone_id, MilestoneSpec(milestone_id=milestone_id))
        if template_id not in spec.templates:
            spec.templates.append(template_id)
        if source_value and not spec.default_source:
            spec.default_source = source_value
        spec.expected_patch = _merge_expected_patch(spec.expected_patch, normalized_patch)
        if normalized_tags:
            merged_tags = set(spec.coverage_tags)
            merged_tags.update(normalized_tags)
            spec.coverage_tags = list(sorted(merged_tags))

    for spec in milestone_map.values():
        spec.templates = _normalise_list(spec.templates)
        spec.coverage_tags = _normalise_list(spec.coverage_tags)

    return TemplateCatalog(version=version, templates=template_map, milestones=milestone_map)


def build_patch_for_milestones(
    milestone_ids: Iterable[str],
    *,
    notes: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Construct a StoryState patch payload for the provided milestones."""

    catalog = get_template_catalog()
    patch: Dict[str, Any] = {}
    milestones_payload: Dict[str, Dict[str, Any]] = {}
    coverage: Dict[str, bool] = {}

    for milestone_id in milestone_ids:
        if not milestone_id:
            continue
        spec = catalog.milestones.get(milestone_id)
        if spec is None:
            continue
        entry: Dict[str, Any] = {"status": "complete"}
        if spec.default_source:
            entry["source"] = spec.default_source
        note = notes.get(milestone_id) if notes else None
        if note:
            entry["note"] = note
        milestones_payload[milestone_id] = entry
        if spec.expected_patch:
            for field, values in spec.expected_patch.items():
                if not values:
                    continue
                patch.setdefault(field, []).extend(values)
        if spec.coverage_tags:
            for tag in spec.coverage_tags:
                if tag:
                    coverage[tag] = True

    if not milestones_payload:
        return {}

    for field, values in list(patch.items()):
        if not isinstance(values, list):
            continue
        patch[field] = _normalise_list(values)

    if coverage:
        existing = patch.setdefault("coverage", {})
        for key, value in coverage.items():
            existing[key] = bool(value)

    patch["milestones"] = milestones_payload
    return patch


__all__ = [
    "TemplateCatalog",
    "TemplateEntry",
    "MilestoneSpec",
    "get_template_catalog",
    "build_patch_for_milestones",
]
