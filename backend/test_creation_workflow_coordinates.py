from app.services import creation_workflow
from app.core.intent_creation import CreationIntentDecision


def _decision_with_material(token: str) -> CreationIntentDecision:
    return CreationIntentDecision(
        is_creation=True,
        confidence=0.6,
        reasons=["action:place"],
        slots={"materials": [token]},
    )


def test_generate_plan_uses_explicit_coordinates():
    decision = _decision_with_material("minecraft:amethyst_block")
    plan_result = creation_workflow.generate_plan(
        decision,
        message="在坐标 12 65 -3 放置 minecraft:amethyst_block",
    )

    assert plan_result.plan.patch_templates, "expected at least one patch template"
    template = plan_result.plan.patch_templates[0]
    commands = template.world_patch.get("mc", {}).get("commands", [])
    assert commands == ["setblock 12 65 -3 minecraft:amethyst_block"]
    metadata = template.world_patch.get("metadata", {})
    assert metadata.get("coordinates") == {"x": 12, "y": 65, "z": -3}
    assert metadata.get("block_id") == "minecraft:amethyst_block"
    assert metadata.get("source") == "explicit_coordinates"
