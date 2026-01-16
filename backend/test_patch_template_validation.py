import json
from pathlib import Path

import pytest

from app.core.creation import (
    CreationTransformer,
    ResourceCatalog,
    validate_patch_template,
)
from app.core.intent_creation import CreationIntentDecision

GOLDEN_DIR = Path(__file__).parent / "tests" / "golden_exhibits"


@pytest.fixture(scope="module")
def transformer() -> CreationTransformer:
    catalog = ResourceCatalog()
    catalog.invalidate()
    return CreationTransformer(catalog=catalog)


def test_patch_template_schema_roundtrip(transformer: CreationTransformer) -> None:
    decision = CreationIntentDecision(
        is_creation=True,
        confidence=0.85,
        reasons=["golden"],
        slots={
            "actions": ["build"],
            "materials": ["amethyst"],
        },
    )
    result = transformer.transform(decision)
    payload = result.to_payload()
    template = payload["patch_templates"][0]
    validation = validate_patch_template(template)

    assert validation.execution_tier in {"safe_auto", "needs_confirm", "blocked"}
    assert isinstance(validation.errors, list)


def test_golden_exhibit_template(transformer: CreationTransformer) -> None:
    fixture_path = GOLDEN_DIR / "amethyst_showcase.json"
    expected = json.loads(fixture_path.read_text("utf-8"))

    decision = CreationIntentDecision(
        is_creation=True,
        confidence=0.9,
        reasons=["golden"],
        slots={
            "actions": ["build"],
            "materials": ["amethyst", "lantern"],
        },
    )
    payload = transformer.transform(decision).to_payload()
    generated = {
        "materials": payload["materials"],
        "patch_templates": payload["patch_templates"],
        "execution_tier": payload["execution_tier"],
        "unsafe_steps": payload["unsafe_steps"],
    }
    # Replace volatile metadata like timestamps
    for template in generated["patch_templates"]:
        template["notes"] = []
        template.setdefault("validation", {})
        template["validation"].pop("warnings", None)
        metadata = template.get("world_patch", {}).get("metadata", {})
        metadata.pop("step_description", None)
    assert generated == expected
