import pytest

from app.core.creation import CreationTransformer, ResourceCatalog
from app.core.intent_creation import CreationIntentDecision


@pytest.fixture(scope="module")
def transformer() -> CreationTransformer:
    catalog = ResourceCatalog()
    catalog.invalidate()
    return CreationTransformer(catalog=catalog)


def make_decision(materials, actions=("build",)) -> CreationIntentDecision:
    return CreationIntentDecision(
        is_creation=True,
        confidence=0.82,
        reasons=["test"],
        slots={"materials": list(materials), "actions": list(actions)},
    )


def test_transformer_maps_known_materials(transformer: CreationTransformer) -> None:
    decision = make_decision(["amethyst", "lantern", "redstone"])
    result = transformer.transform(decision)
    payload = result.to_payload()

    assert payload["action"] == "build"
    assert payload["confidence"] >= 0.45
    resolved = [material for material in payload["materials"] if material["status"] == "resolved"]
    resource_ids = {material["resource_id"] for material in resolved}
    assert "minecraft:amethyst_block" in resource_ids
    assert "minecraft:soul_lantern" in resource_ids
    assert "minecraft:redstone_dust" in resource_ids
    steps = payload.get("steps", [])
    assert steps
    assert any(
        step.get("required_resource") == "minecraft:amethyst_block"
        for step in steps
        if step.get("required_resource")
    )
    assert payload["execution_tier"] in {"safe_auto", "needs_confirm", "blocked"}
    assert "world_damage_risk" in payload["safety_assessment"]
    templates = payload.get("patch_templates", [])
    assert templates
    first_template = templates[0]
    assert first_template["step_id"].startswith("step-")
    assert first_template["world_patch"].get("metadata")
    assert first_template["validation"]["execution_tier"] in {"safe_auto", "needs_confirm", "blocked"}
    assert "step_type" in first_template


def test_transformer_marks_unknown_material(transformer: CreationTransformer) -> None:
    decision = make_decision(["starflower"])
    result = transformer.transform(decision)
    payload = result.to_payload()

    assert payload["materials"][0]["status"] == "unresolved"
    assert any("starflower" in note for note in payload["notes"])
    assert "starflower" in payload["unresolved_tokens"]
    steps = payload.get("steps", [])
    assert steps and steps[0]["status"] == "needs_review"
    templates = payload.get("patch_templates", [])
    assert templates and templates[0]["status"] == "needs_review"
    assert "手动" in "".join(templates[0]["notes"])
    assert payload["execution_tier"] != "safe_auto"
    assert templates[0]["validation"]["execution_tier"] != "safe_auto"


def test_transformer_handles_non_creation(transformer: CreationTransformer) -> None:
    decision = CreationIntentDecision(
        is_creation=False,
        confidence=0.2,
        reasons=["non_creation"],
        slots={"materials": ["amethyst"], "actions": []},
    )
    result = transformer.transform(decision)
    payload = result.to_payload()

    assert payload["action"] == "create"
    assert any("非创造" in note for note in payload["notes"])
    assert payload["steps"][0]["status"] in {"draft", "needs_review"}
    assert payload["patch_templates"][0]["status"] in {"draft", "needs_review"}
    assert payload["execution_tier"] != "safe_auto"
