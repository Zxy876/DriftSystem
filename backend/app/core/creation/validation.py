"""Validation helpers for creation patch templates and execution readiness."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Set

from app.core.world.command_safety import CommandSafetyReport, analyze_commands


STEP_TYPES: Sequence[str] = (
    "block_placement",
    "mod_function",
    "entity_spawn",
    "manual_review",
    "custom_command",
)

_PLACEHOLDER_PATTERN = re.compile(r"\{([a-z0-9_]+)\}")

_REQUIRED_FIELDS = {
    "block_placement": ("resource_id",),
    "mod_function": ("resource_id",),
    "entity_spawn": ("resource_id",),
    "manual_review": tuple(),
    "custom_command": tuple(),
}


@dataclass
class PatchTemplateValidationResult:
    """Outcome of validating a patch template against execution rules."""

    errors: List[str]
    warnings: List[str]
    execution_tier: str
    missing_fields: List[str]
    unsafe_placeholders: List[str]

    def to_payload(self) -> Dict[str, object]:
        return {
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "execution_tier": self.execution_tier,
            "missing_fields": list(self.missing_fields),
            "unsafe_placeholders": list(self.unsafe_placeholders),
        }


def detect_placeholders(commands: Iterable[str]) -> Set[str]:
    placeholders: Set[str] = set()
    for command in commands:
        for match in _PLACEHOLDER_PATTERN.finditer(command):
            placeholders.add(match.group(1))
    return placeholders


def classify_step_type(commands: Iterable[str], step_status: str) -> str:
    for command in commands:
        lowered = command.strip().lower()
        if lowered.startswith("summon "):
            return "entity_spawn"
        if any(lowered.startswith(prefix) for prefix in ("setblock ", "fill ", "clone ")):
            return "block_placement"
        if " function " in f" {lowered} " or lowered.startswith("function "):
            return "mod_function"
    if step_status != "resolved":
        return "manual_review"
    if not commands:
        return "manual_review"
    return "custom_command"


def validate_patch_template(template: Dict[str, object]) -> PatchTemplateValidationResult:
    errors: List[str] = []
    warnings: List[str] = []
    missing_fields: List[str] = []

    step_type = str(template.get("step_type") or "manual_review")
    if step_type not in STEP_TYPES:
        errors.append(f"step_type_unsupported:{step_type}")
        step_type = "manual_review"

    status = str(template.get("status") or "draft")
    commands = [
        str(cmd)
        for cmd in template.get("world_patch", {}).get("mc", {}).get("commands", [])
        if isinstance(cmd, str)
    ]

    safety_report: CommandSafetyReport = analyze_commands(commands)
    errors.extend(f"command:{item}" for item in safety_report.errors)
    warnings.extend(f"command:{item}" for item in safety_report.warnings)

    metadata = template.get("world_patch", {}).get("metadata", {})
    required_fields = _REQUIRED_FIELDS.get(step_type, tuple())
    for field in required_fields:
        if not isinstance(metadata, dict) or field not in metadata:
            missing_fields.append(field)

    placeholders = detect_placeholders(commands)
    unsafe_placeholders: List[str] = []
    if status == "resolved" and placeholders:
        warnings.append("command_contains_placeholders")
        unsafe_placeholders = sorted(placeholders)

    execution_tier = "safe_auto"
    if errors:
        execution_tier = "blocked"
    elif missing_fields or placeholders or status != "resolved":
        execution_tier = "needs_confirm"
    elif warnings:
        execution_tier = "needs_confirm"

    return PatchTemplateValidationResult(
        errors=errors,
        warnings=warnings,
        execution_tier=execution_tier,
        missing_fields=missing_fields,
        unsafe_placeholders=unsafe_placeholders,
    )
