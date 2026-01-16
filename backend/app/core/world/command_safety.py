"""Command safety utilities for world patch execution (Phase 3 groundwork)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List


@dataclass
class CommandSafetyReport:
    """Structured result describing command validation findings."""

    errors: List[str]
    warnings: List[str]

    def merge(self, other: "CommandSafetyReport") -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)


_ALLOWED_PREFIXES = (
    "setblock ",
    "fill ",
    "clone ",
    "summon ",
    "execute ",
    "function ",
    "particle ",
    "title ",
    "tellraw ",
)

_BLOCKED_TOKENS = (
    ";",
    "&&",
    "||",
    "`",
    "$(",
    "\n",
    "\r",
)

_BLOCKED_COMMANDS = (
    "op ",
    "deop ",
    "stop",
    "reload",
)

_ALLOWED_FUNCTION_PATTERN = re.compile(r"^function\s+[a-z0-9_.:-]+$", re.IGNORECASE)
_ALLOWED_EXECUTE_PATTERN = re.compile(
    r"^execute(\s+(as|at|in|positioned|rotated|facing|anchored|align|unless|if|store|summon|run|on)\b)+",
    re.IGNORECASE,
)
_ALLOWED_GENERAL_PATTERN = re.compile(r"^[a-z0-9_{}:^~.\-\s,/|=\[\]]+$", re.IGNORECASE)


def _report_for_command(command: str) -> CommandSafetyReport:
    errors: List[str] = []
    warnings: List[str] = []

    stripped = command.strip()
    lowered = stripped.lower()

    if not stripped:
        return CommandSafetyReport(errors, warnings)

    for token in _BLOCKED_TOKENS:
        if token in stripped:
            errors.append(f"command_contains_disallowed_token:{token}")

    for forbidden in _BLOCKED_COMMANDS:
        if lowered.startswith(forbidden):
            errors.append(f"command_blacklisted:{forbidden.strip()}")

    if not any(lowered.startswith(prefix.strip()) for prefix in _ALLOWED_PREFIXES):
        warnings.append("command_prefix_unlisted")

    if stripped.startswith("function ") and not _ALLOWED_FUNCTION_PATTERN.match(stripped):
        errors.append("command_function_identifier_invalid")

    if stripped.startswith("execute ") and not _ALLOWED_EXECUTE_PATTERN.match(stripped):
        warnings.append("command_execute_pattern_unverified")

    if not _ALLOWED_GENERAL_PATTERN.match(stripped):
        warnings.append("command_contains_unexpected_characters")

    return CommandSafetyReport(errors, warnings)


def analyze_commands(commands: Iterable[str]) -> CommandSafetyReport:
    """Validate that commands comply with the Phase 3 whitelist expectations."""

    aggregate = CommandSafetyReport(errors=[], warnings=[])
    for command in commands:
        aggregate.merge(_report_for_command(command))
    return aggregate
