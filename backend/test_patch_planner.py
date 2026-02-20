"""Tests for PatchPlanner abstract interface and concrete implementations."""

import pytest

from app.core.intent_creation import CreationIntentDecision
from app.core.world.patch_planner import (
    DeterministicPlanner,
    LLMBasedPlanner,
    PatchPlanner,
    sanitize_block_id,
    parse_coordinate_components,
)


def _creation_decision(token: str, confidence: float = 0.8) -> CreationIntentDecision:
    return CreationIntentDecision(
        is_creation=True,
        confidence=confidence,
        reasons=["action:place"],
        slots={"materials": [token]},
    )


def _non_creation_decision() -> CreationIntentDecision:
    return CreationIntentDecision(
        is_creation=False,
        confidence=0.1,
        reasons=[],
        slots={},
    )


# ---------------------------------------------------------------------------
# PatchPlanner is abstract
# ---------------------------------------------------------------------------


def test_patch_planner_is_abstract() -> None:
    with pytest.raises(TypeError):
        PatchPlanner()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# DeterministicPlanner
# ---------------------------------------------------------------------------


class TestDeterministicPlanner:
    def setup_method(self) -> None:
        self.planner = DeterministicPlanner()

    def test_returns_none_for_non_creation_decision(self) -> None:
        result = self.planner.plan(
            _non_creation_decision(),
            message="setblock 1 2 3 minecraft:stone",
        )
        assert result is None

    def test_returns_none_when_message_is_none(self) -> None:
        result = self.planner.plan(_creation_decision("minecraft:stone"), message=None)
        assert result is None

    def test_returns_none_when_no_coordinates_in_message(self) -> None:
        result = self.planner.plan(
            _creation_decision("minecraft:stone"),
            message="放置 minecraft:stone 在某处",
        )
        assert result is None

    def test_extracts_block_from_slot_and_triple_coord(self) -> None:
        decision = _creation_decision("minecraft:amethyst_block")
        result = self.planner.plan(
            decision,
            message="在坐标 12 65 -3 放置 minecraft:amethyst_block",
        )

        assert result is not None
        plan = result.plan
        assert plan.execution_tier == "safe_auto"
        assert len(plan.patch_templates) == 1
        template = plan.patch_templates[0]
        commands = template.world_patch.get("mc", {}).get("commands", [])
        assert commands == ["setblock 12 65 -3 minecraft:amethyst_block"]
        meta = template.world_patch.get("metadata", {})
        assert meta["block_id"] == "minecraft:amethyst_block"
        assert meta["coordinates"] == {"x": 12, "y": 65, "z": -3}
        assert meta["source"] == "explicit_coordinates"

    def test_extracts_block_from_message_scan_when_slot_has_no_minecraft_prefix(self) -> None:
        decision = CreationIntentDecision(
            is_creation=True,
            confidence=0.7,
            reasons=["action:place"],
            slots={"materials": ["stone"]},
        )
        result = self.planner.plan(
            decision,
            message="在坐标 0 64 0 放 minecraft:stone",
        )

        assert result is not None
        plan = result.plan
        commands = plan.patch_templates[0].world_patch.get("mc", {}).get("commands", [])
        assert commands == ["setblock 0 64 0 minecraft:stone"]

    def test_extracts_component_coordinates(self) -> None:
        decision = _creation_decision("minecraft:grass_block")
        result = self.planner.plan(
            decision,
            message="x=10 y=64 z=-5 放置 minecraft:grass_block",
        )

        assert result is not None
        commands = result.plan.patch_templates[0].world_patch.get("mc", {}).get("commands", [])
        assert commands == ["setblock 10 64 -5 minecraft:grass_block"]

    def test_confidence_is_clamped_to_minimum_0_75(self) -> None:
        decision = _creation_decision("minecraft:stone", confidence=0.1)
        result = self.planner.plan(
            decision,
            message="在坐标 0 0 0 放置 minecraft:stone",
        )

        assert result is not None
        assert result.plan.confidence >= 0.75


# ---------------------------------------------------------------------------
# LLMBasedPlanner
# ---------------------------------------------------------------------------


class TestLLMBasedPlanner:
    def test_uses_provided_transformer(self) -> None:
        class _FakeTransformer:
            called_with = None

            def transform(self, decision):
                _FakeTransformer.called_with = decision
                from app.core.creation.transformer import CreationPlan, CreationPlanResult

                return CreationPlanResult(
                    plan=CreationPlan(
                        action="create",
                        materials=[],
                        confidence=0.5,
                        summary="fake",
                    ),
                    snapshot_generated_at=None,
                )

        transformer = _FakeTransformer()
        planner = LLMBasedPlanner(transformer)
        decision = _creation_decision("minecraft:stone")
        result = planner.plan(decision, message="something")

        assert result is not None
        assert _FakeTransformer.called_with is decision

    def test_always_returns_a_result_for_creation_intent(self) -> None:
        planner = LLMBasedPlanner()
        decision = _creation_decision("minecraft:stone")
        result = planner.plan(decision)
        assert result is not None


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


class TestSanitizeBlockId:
    def test_valid_block_id(self) -> None:
        assert sanitize_block_id("minecraft:stone") == "minecraft:stone"

    def test_normalizes_to_lowercase(self) -> None:
        assert sanitize_block_id("Minecraft:Stone") == "minecraft:stone"

    def test_raises_on_empty(self) -> None:
        with pytest.raises(ValueError, match="empty_block_id"):
            sanitize_block_id("")

    def test_raises_on_invalid_pattern(self) -> None:
        with pytest.raises(ValueError, match="invalid_block_id"):
            sanitize_block_id("stone")


class TestParseCoordinateComponents:
    def test_parses_xyz_components(self) -> None:
        assert parse_coordinate_components("x=1 y=2 z=3") == (1, 2, 3)

    def test_returns_none_when_incomplete(self) -> None:
        assert parse_coordinate_components("x=1 y=2") is None

    def test_rounds_floats(self) -> None:
        assert parse_coordinate_components("x=1.7 y=2.3 z=-0.6") == (2, 2, -1)
