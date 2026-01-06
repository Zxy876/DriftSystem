"""Narrative chat ingestion into the Ideal City adjudication pipeline.

This module provides a lightweight extractor that reads structured guidance
from storyline chat messages and turns them into ``DeviceSpecSubmission``
objects. The goal is to let narrative conversations populate the same
adjudication queue used by the CityPhone UI without duplicating validation
logic. The extractor currently relies on simple rule-based parsing so it can
ship quickly and remain deterministic; confidence scoring and missing-field
tracking ensure weak payloads do not pollute the pipeline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

from pydantic import BaseModel, Field

from .build_plan import PlayerPose
from .device_spec import sanitize_lines


# Tags recognised in narrative chat. Both Chinese and English aliases are
# supported so story authors can mix in whichever feels natural.
FIELD_ALIASES: Dict[str, str] = {
    "愿景": "vision",
    "vision": "vision",
    "目标": "vision",
    "构想": "vision",
    "方案": "vision",
    "蓝图": "vision",
    "战略": "vision",
    "行动": "actions",
    "steps": "actions",
    "行动计划": "actions",
    "执行路径": "actions",
    "执行步骤": "actions",
    "任务": "actions",
    "方案路径": "actions",
    "资源": "resources",
    "资源清单": "resources",
    "resources": "resources",
    "材料": "resources",
    "物资": "resources",
    "设备": "resources",
    "工具": "resources",
    "支持": "resources",
    "限制": "constraints",
    "约束": "constraints",
    "阻碍": "constraints",
    "挑战": "constraints",
    "constraints": "constraints",
    "地点": "location",
    "位置": "location",
    "落点": "location",
    "现场": "location",
    "坐标": "location",
    "location": "location",
    "成功": "success",
    "成功指标": "success",
    "成效": "success",
    "成果": "success",
    "success": "success",
    "风险": "risks",
    "风险登记": "risks",
    "隐患": "risks",
    "risks": "risks",
    "备注": "notes",
    "补充": "notes",
    "tips": "notes",
    "notes": "notes",
}


LINE_FIELD_PATTERN = re.compile(
    r"^[\s\-•*\[【\(（]*(?P<tag>[\w\u4e00-\u9fff]+)[\]】）\)]*[\s：:]+(?P<value>.+)$"
)
POSE_COORD_PATTERN = re.compile(
    r"(?i)\b(x|坐标x)\s*[:=]\s*(-?\d+(?:\.\d+)?)|"
    r"\b(y|坐标y)\s*[:=]\s*(-?\d+(?:\.\d+)?)|"
    r"\b(z|坐标z)\s*[:=]\s*(-?\d+(?:\.\d+)?)"
)
WORLD_PATTERN = re.compile(r"(?i)\b(world|维度)\s*[:=]\s*([\w_\-]+)")
YAW_PATTERN = re.compile(r"(?i)\b(yaw)\s*[:=]\s*(-?\d+(?:\.\d+)?)")
PITCH_PATTERN = re.compile(r"(?i)\b(pitch)\s*[:=]\s*(-?\d+(?:\.\d+)?)")


def _split_items(value: str) -> List[str]:
    """Split a human sentence into list items."""

    if not value:
        return []
    value = value.strip()
    separators = ["；", ";", "、", "\n", "|", "，", ","]
    for sep in separators:
        if sep in value:
            parts = [chunk.strip() for chunk in value.split(sep)]
            return [chunk for chunk in parts if chunk]
    return [value.strip()] if value.strip() else []


def _normalise_items(items: Iterable[str]) -> List[str]:
    return sanitize_lines(list(items))


@dataclass
class NarrativeExtraction:
    """Structured data parsed from a chat message."""

    vision: List[str]
    actions: List[str]
    resources: List[str]
    constraints: List[str]
    success: List[str]
    risks: List[str]
    notes: List[str]
    location_hint: Optional[str]
    pose: Optional[PlayerPose]
    confidence: float
    missing_fields: List[str]
    raw_fields: Dict[str, str]

    @property
    def has_core_fields(self) -> bool:
        return bool(self.vision and len(self.actions) >= 1)

    @property
    def needs_manual_review(self) -> bool:
        # Flag for review if location or resources are missing even when
        # narrative looks sound; this keeps parity with CityPhone expectations.
        return not self.resources or (self.pose is None and not self.location_hint)


class NarrativeChatEvent(BaseModel):
    """Incoming chat snippet eligible for adjudication parsing."""

    player_id: str
    message: str
    scenario_id: Optional[str] = Field(default=None, description="Scenario hint")
    channel: Optional[str] = Field(default=None, description="Chat channel identifier")
    context_id: Optional[str] = Field(default=None, description="Storyline context id")
    timestamp: Optional[datetime] = Field(default=None, description="Client-side timestamp")


class NarrativeIngestionResponse(BaseModel):
    status: str
    confidence: float
    missing_fields: List[str]
    message: Optional[str] = None
    source_fields: Dict[str, str] = Field(default_factory=dict)
    submission: Optional[dict] = None
    ruling: Optional[dict] = None
    notice: Optional[dict] = None
    guidance: Optional[List[dict]] = None
    build_plan: Optional[dict] = None
    state: Optional[dict] = None


class NarrativeFieldExtractor:
    """Simple rule-based extractor for structured storyline chat."""

    def extract(self, message: str) -> NarrativeExtraction:
        message = message.strip()
        if not message:
            return NarrativeExtraction(
                vision=[],
                actions=[],
                resources=[],
                constraints=[],
                success=[],
                risks=[],
                notes=[],
                location_hint=None,
                pose=None,
                confidence=0.0,
                missing_fields=["vision", "actions"],
                raw_fields={},
            )

        raw_fields: Dict[str, str] = {}
        evaluated_lines: List[str] = []
        paragraph_buffer: List[str] = []

        for raw_line in message.splitlines():
            line = raw_line.strip()
            if not line:
                if paragraph_buffer:
                    evaluated_lines.append(" ".join(paragraph_buffer))
                    paragraph_buffer = []
                continue
            matched = LINE_FIELD_PATTERN.match(line)
            if matched:
                evaluated_lines.append(line)
                continue
            paragraph_buffer.append(line)

        if paragraph_buffer:
            evaluated_lines.append(" ".join(paragraph_buffer))

        for line in evaluated_lines:
            if not line:
                continue
            match = LINE_FIELD_PATTERN.match(line)
            if not match:
                continue
            line = line.strip()
            if not line:
                continue
            match = LINE_FIELD_PATTERN.match(line)
            if not match:
                continue
            tag = match.group("tag").strip().lower()
            tag = FIELD_ALIASES.get(tag, tag)
            value = match.group("value").strip()
            if tag not in raw_fields:
                raw_fields[tag] = value

        # Vision fallback: use first paragraph if explicit tag missing
        if "vision" not in raw_fields:
            # Fall back to the first meaningful paragraph instead of the
            # literal first line so descriptive chat still forms a vision.
            fallback_text = ""
            for chunk in evaluated_lines:
                if not chunk:
                    continue
                candidate = chunk.strip("-•* 　")
                if candidate:
                    fallback_text = candidate
                    break
            if not fallback_text:
                fallback_text = message.strip().splitlines()[0].strip() if message.strip() else ""
            raw_fields["vision"] = fallback_text

        vision = _normalise_items(_split_items(raw_fields.get("vision", "")))
        actions = _normalise_items(_split_items(raw_fields.get("actions", "")))
        resources = _normalise_items(_split_items(raw_fields.get("resources", "")))
        constraints = _normalise_items(_split_items(raw_fields.get("constraints", "")))
        success = _normalise_items(_split_items(raw_fields.get("success", "")))
        risks = _normalise_items(_split_items(raw_fields.get("risks", "")))
        notes = _normalise_items(_split_items(raw_fields.get("notes", "")))

        location_hint = raw_fields.get("location")
        pose = self._parse_pose(location_hint)
        if pose is not None:
            location_hint = location_hint

        recognised = sum(
            1 for bucket in [vision, actions, resources, constraints, success, risks] if bucket
        )
        total_slots = 6
        confidence = recognised / total_slots if total_slots else 0.0

        missing_fields: List[str] = []
        if not vision:
            missing_fields.append("vision")
        if not actions:
            missing_fields.append("actions")
        if not resources:
            missing_fields.append("resources")
        if pose is None and not location_hint:
            missing_fields.append("location")

        return NarrativeExtraction(
            vision=vision,
            actions=actions,
            resources=resources,
            constraints=constraints,
            success=success,
            risks=risks,
            notes=notes,
            location_hint=location_hint,
            pose=pose,
            confidence=confidence,
            missing_fields=missing_fields,
            raw_fields=raw_fields,
        )

    def _parse_pose(self, value: Optional[str]) -> Optional[PlayerPose]:
        if not value:
            return None

        coords: Dict[str, float] = {}
        for match in POSE_COORD_PATTERN.finditer(value):
            groups = match.groups()
            # Pattern yields groups in (tag, x, tag, y, tag, z)
            if groups[1] is not None:
                coords["x"] = float(groups[1])
            if groups[3] is not None:
                coords["y"] = float(groups[3])
            if groups[5] is not None:
                coords["z"] = float(groups[5])

        if not {"x", "y", "z"}.issubset(coords):
            return None

        world_match = WORLD_PATTERN.search(value)
        world = world_match.group(2) if world_match else "world"
        yaw_match = YAW_PATTERN.search(value)
        pitch_match = PITCH_PATTERN.search(value)

        return PlayerPose(
            world=world,
            x=coords["x"],
            y=coords["y"],
            z=coords["z"],
            yaw=float(yaw_match.group(2)) if yaw_match else 0.0,
            pitch=float(pitch_match.group(2)) if pitch_match else 0.0,
        )


class NarrativeChatIngestor:
    """Facade coordinating extraction and confidence checks."""

    def __init__(self) -> None:
        self._extractor = NarrativeFieldExtractor()

    def process(self, event: NarrativeChatEvent) -> NarrativeExtraction:
        return self._extractor.extract(event.message)
