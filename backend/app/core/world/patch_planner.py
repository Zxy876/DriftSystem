"""PatchPlanner abstraction for pluggable patch-generation strategies.

Current architecture verdict: B – LLM 驱动 + 执行安全层
  - Core adjudication and safety validation are fully rule-based.
  - Build-plan / patch generation previously resided in the service layer
    (creation_workflow.py) with no shared interface between the LLM path and
    the deterministic path.

Migration goal: introduce a PatchPlanner seam so the two strategies can be
swapped or chained without touching the downstream execution chain
(PatchExecutor → PlanExecutor → RCON).

Key code paths:
  Before: services/creation_workflow.py::generate_plan
            → _extract_explicit_block_plan  (deterministic, coordinate-based)
            → _creation_transformer.transform  (LLM-backed catalog lookup)
  After:  services/creation_workflow.py::generate_plan
            → DeterministicPlanner.plan  (explicit-coordinate handling)
            → LLMBasedPlanner.plan       (transformer / LLM path)

Execution chain (unchanged):
  generate_plan → dry_run_plan (PatchExecutor) → auto_execute_plan (PlanExecutor)
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Dict, Optional, Sequence, Tuple

from app.core.creation.transformer import (
    CreationPlan,
    CreationPlanMaterial,
    CreationPlanResult,
    CreationPlanStep,
    CreationPatchTemplate,
)
from app.core.intent_creation import CreationIntentDecision


# ---------------------------------------------------------------------------
# Shared parsing constants (previously private to creation_workflow.py)
# ---------------------------------------------------------------------------

BLOCK_ID_PATTERN = re.compile(r"minecraft:[a-z0-9_./\-]+", re.IGNORECASE)

COORD_TRIPLE_PATTERN = re.compile(
    r"(?:坐标|坐標|coordinates?)\s*[:：]?\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

COORD_COMPONENT_PATTERN = re.compile(
    r"(?:(?:坐标)?\s*(x|y|z)\s*[:=]\s*(-?\d+(?:\.\d+)?))",
    re.IGNORECASE,
)


def sanitize_block_id(block_id: str) -> str:
    """Return a normalised, validated Minecraft block ID.

    Raises :exc:`ValueError` when the input is empty or does not match the
    expected ``minecraft:*`` namespace pattern.
    """
    candidate = (block_id or "").strip().lower()
    if not candidate:
        raise ValueError("empty_block_id")
    if not BLOCK_ID_PATTERN.fullmatch(candidate):
        raise ValueError(f"invalid_block_id:{block_id}")
    return candidate


def parse_coordinate_components(message: str) -> Optional[Tuple[int, int, int]]:
    """Extract x/y/z coordinates from labelled components such as ``x=10 y=64 z=-5``."""
    components: Dict[str, float] = {}
    for match in COORD_COMPONENT_PATTERN.finditer(message):
        axis = match.group(1).lower()
        value = match.group(2)
        try:
            components[axis] = float(value)
        except (TypeError, ValueError):
            continue
    if {"x", "y", "z"}.issubset(components):
        return tuple(int(round(components[axis])) for axis in ("x", "y", "z"))
    return None


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------


class PatchPlanner(ABC):
    """Abstract interface for generating a :class:`CreationPlan` from an intent.

    Implementations must be stateless or thread-safe so they can be shared
    across requests.
    """

    @abstractmethod
    def plan(
        self,
        decision: CreationIntentDecision,
        *,
        message: Optional[str] = None,
    ) -> Optional[CreationPlanResult]:
        """Return a :class:`CreationPlanResult` or ``None`` if not applicable.

        Returning ``None`` signals that this planner cannot handle the input
        and the caller should try the next planner in the chain.
        """


# ---------------------------------------------------------------------------
# LLM-backed implementation
# ---------------------------------------------------------------------------


class LLMBasedPlanner(PatchPlanner):
    """Generate a plan via the default resource transformer (LLM-backed catalog lookup).

    This planner always returns a result – it should be used as the last
    fallback in a chain.
    """

    def __init__(self, transformer=None) -> None:
        if transformer is None:
            from app.core.creation import load_default_transformer
            transformer = load_default_transformer()
        self._transformer = transformer

    def plan(
        self,
        decision: CreationIntentDecision,
        *,
        message: Optional[str] = None,
    ) -> Optional[CreationPlanResult]:
        return self._transformer.transform(decision)


# ---------------------------------------------------------------------------
# Deterministic (rule-based) implementation
# ---------------------------------------------------------------------------


class DeterministicPlanner(PatchPlanner):
    """Rule-based planner for explicit block-placement requests.

    Handles messages that contain both a ``minecraft:*`` block ID and numeric
    coordinates, producing a ``safe_auto`` patch without any LLM involvement.
    Returns ``None`` when the input does not include sufficient information,
    allowing a downstream :class:`LLMBasedPlanner` to handle the request.
    """

    def plan(
        self,
        decision: CreationIntentDecision,
        *,
        message: Optional[str] = None,
    ) -> Optional[CreationPlanResult]:
        if not decision.is_creation or not message:
            return None
        return self._extract_explicit_block_plan(decision, message)

    @classmethod
    def _extract_explicit_block_plan(
        cls,
        decision: CreationIntentDecision,
        message: str,
    ) -> Optional[CreationPlanResult]:
        block_id: Optional[str] = None
        material_tokens: Sequence[str] = tuple(
            decision.slots.get("materials", []) if isinstance(decision.slots, dict) else []
        )
        for token in material_tokens:
            candidate = str(token).strip().lower()
            if candidate.startswith("minecraft:"):
                block_id = candidate
                break

        if block_id is None:
            match = BLOCK_ID_PATTERN.search(message)
            if match:
                block_id = match.group(0).lower()

        if block_id is None:
            return None

        coords: Optional[Tuple[int, int, int]] = None
        triple_match = COORD_TRIPLE_PATTERN.search(message)
        if triple_match:
            try:
                coords = tuple(int(round(float(group))) for group in triple_match.groups())
            except ValueError:
                coords = None
        if coords is None:
            coords = parse_coordinate_components(message)
        if coords is None:
            return None

        plan = cls._build_block_plan(
            block_id, coords, confidence=decision.confidence, source="explicit_coordinates"
        )
        return CreationPlanResult(plan=plan, snapshot_generated_at=None)

    @classmethod
    def _build_block_plan(
        cls,
        block_id: str,
        coords: Tuple[int, int, int],
        *,
        confidence: float,
        source: str = "chat",
    ) -> CreationPlan:
        sanitized = sanitize_block_id(block_id)
        command = f"setblock {coords[0]} {coords[1]} {coords[2]} {sanitized}"
        clamped_confidence = max(confidence, 0.75)

        material = CreationPlanMaterial(
            token=sanitized,
            resource_id=sanitized,
            label=sanitized,
            status="resolved",
            confidence=clamped_confidence,
            quantity=1,
            tags=["explicit_coordinate"],
        )
        step = CreationPlanStep(
            step_id="step-1",
            title=f"Set {sanitized} at {coords[0]} {coords[1]} {coords[2]}",
            description="根据玩家提供的坐标放置方块。",
            status="resolved",
            step_type="block_command",
            commands=[command],
            required_resource=sanitized,
            tags=["explicit_coordinate"],
        )
        template = CreationPatchTemplate(
            step_id=step.step_id,
            template_id="explicit:setblock",
            status="resolved",
            summary=step.title,
            step_type=step.step_type,
            world_patch={
                "mc": {"commands": [command]},
                "metadata": {
                    "source": source,
                    "coordinates": {"x": coords[0], "y": coords[1], "z": coords[2]},
                    "block_id": sanitized,
                },
            },
            mod_hooks=[],
            requires_player_pose=False,
            notes=["聊天坐标直接生成 setblock 指令。"],
            tags=["explicit_coordinate"],
        )

        return CreationPlan(
            action="place_block",
            materials=[material],
            confidence=clamped_confidence,
            summary=f"Place {sanitized} at {coords[0]} {coords[1]} {coords[2]}",
            steps=[step],
            patch_templates=[template],
            notes=[f"source:{source}"],
            execution_tier="safe_auto",
            validation_errors=[],
            validation_warnings=[],
            missing_fields=[],
            unsafe_steps=[],
            safety_assessment={
                "world_damage_risk": "low",
                "reversibility": True,
                "requires_confirmation": False,
            },
        )


__all__ = [
    "BLOCK_ID_PATTERN",
    "COORD_COMPONENT_PATTERN",
    "COORD_TRIPLE_PATTERN",
    "DeterministicPlanner",
    "LLMBasedPlanner",
    "PatchPlanner",
    "parse_coordinate_components",
    "sanitize_block_id",
]
