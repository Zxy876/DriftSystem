"""Utilities for sanitising Minecraft resource identifiers in generated commands."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Iterable, List, Tuple

logger = logging.getLogger(__name__)

# Allowable characters for different ResourceLocation segments
_NAMESPACE_INVALID = re.compile(r"[^a-z0-9._-]")
_PATH_INVALID = re.compile(r"[^a-z0-9/._-]")
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")

_RESOURCE_CANDIDATE_CHARS = re.compile(r"^[A-Za-z0-9_.:/-]+$")
_RESOURCE_IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9_.-]+:[a-z0-9_/.-]+$")

# Pattern to find candidate resource identifiers within command strings. The third
# capturing group keeps any trailing characters (e.g. NBT payload) untouched while
# still allowing us to clean the identifier.
_RESOURCE_TOKEN_PATTERN = re.compile(
    r"\b([a-z0-9_.-]+):([a-z0-9_/.-]*)([^\s]*)",
    re.IGNORECASE,
)


def sanitize_resource_location(raw: str, *, context: str = "") -> str:
    """Return a ResourceLocation containing only safe characters.

    The namespace portion allows ``[a-z0-9._-]`` while the path allows
    ``[a-z0-9/._-]``. Any other character is replaced with ``_``. Control
    characters are stripped entirely. The result is lower-cased to follow
    vanilla conventions.
    """

    if not isinstance(raw, str):
        return ""

    original = raw
    text = _CONTROL_CHARS.sub("", raw).strip().lower()
    namespace = ""
    path = text
    if ":" in text:
        namespace, path = text.split(":", 1)

    namespace = _NAMESPACE_INVALID.sub("_", namespace)
    path = _PATH_INVALID.sub("_", path)

    namespace = namespace.strip("._-/")
    path = path.strip("._-/")

    if not path:
        path = "unknown"
    if namespace:
        sanitized = f"{namespace}:{path}"
    else:
        sanitized = path

    if sanitized != text:
        _log_resource_change(original, sanitized, context)
    return sanitized


def sanitize_command_list(commands: Iterable[str], *, context: str = "") -> Tuple[List[str], List[str]]:
    """Sanitise resource identifiers inside command strings.

    Returns the cleaned commands together with a list describing each change.
    """

    cleaned_commands: List[str] = []
    changes: List[str] = []
    context_label = f"[{context}]" if context else ""

    for index, command in enumerate(commands):
        if not isinstance(command, str):
            continue
        original = command
        sanitized = _CONTROL_CHARS.sub("", command)

        def _replace(match: re.Match[str]) -> str:
            namespace = match.group(1)
            path = match.group(2)
            suffix = match.group(3) or ""
            token = f"{namespace}:{path}" if path else namespace
            cleaned = sanitize_resource_location(token, context=f"{context_label}cmd#{index}")
            return f"{cleaned}{suffix}"

        sanitized = _RESOURCE_TOKEN_PATTERN.sub(_replace, sanitized)

        if sanitized != original:
            snippet = original.strip()
            after = sanitized.strip()
            changes.append(f"{context_label}#{index}: {snippet!r} -> {after!r}")
        cleaned_commands.append(sanitized)

    if changes:
        logger.warning("command_resources_sanitized%s: %s", context_label, "; ".join(changes))
    return cleaned_commands, changes


def _log_resource_change(original: str, sanitized: str, context: str) -> None:
    if context:
        logger.warning(
            "resource_location_sanitized[%s]: %r -> %r",
            context,
            original,
            sanitized,
        )
    else:
        logger.warning(
            "resource_location_sanitized: %r -> %r",
            original,
            sanitized,
        )


def sanitize_world_patch(world_patch: Dict[str, Any], *, context: str = "") -> Dict[str, Any]:
    """Return a copy of the world_patch dictionary with commands sanitised.

    This acts as a final safety net before responses are returned to the
    frontend. If any commands still contain control characters or illegal
    identifiers we log a warning so the offending pipeline can be traced.
    """

    if not isinstance(world_patch, dict):
        return {}

    sanitized_patch: Dict[str, Any] = {}
    for key, value in world_patch.items():
        sanitized_patch[key] = value

    context_label = context or "world_patch"

    mc_section = sanitized_patch.get("mc")
    if isinstance(mc_section, dict):
        updated_mc = mc_section
        commands = mc_section.get("commands")
        if isinstance(commands, Iterable) and not isinstance(commands, (str, bytes)):
            raw_commands = [str(cmd) for cmd in commands if isinstance(cmd, str)]
            cleaned_commands, changes = sanitize_command_list(raw_commands, context=context_label)
            updated_mc = dict(mc_section)
            updated_mc["commands"] = cleaned_commands
            sanitized_patch["mc"] = updated_mc
            if changes:
                logger.warning(
                    "world_patch_commands_sanitized[%s]: %s",
                    context_label,
                    "; ".join(changes),
                )
        _log_invalid_resource_tokens(updated_mc, base_context=f"{context_label}.mc")
    elif isinstance(mc_section, list):
        for index, entry in enumerate(mc_section):
            if isinstance(entry, dict):
                _log_invalid_resource_tokens(entry, base_context=f"{context_label}.mc[{index}]")
    return sanitized_patch


def _log_invalid_resource_tokens(node: Any, *, base_context: str) -> None:
    """Depth-first scan looking for strings that resemble resource identifiers.

    We only emit warnings for strings that contain a colon, are made up of the
    characters typically permitted in namespaced identifiers, but do *not*
    satisfy the vanilla ``namespace:path`` pattern. This keeps false positives
    low while surfacing suspicious tokens that may still escape the normal
    command sanitiser.
    """

    def visit(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}.{key}" if path else str(key)
                visit(child, child_path)
            return
        if isinstance(value, list):
            for index, child in enumerate(value):
                child_path = f"{path}[{index}]" if path else f"[{index}]"
                visit(child, child_path)
            return
        if isinstance(value, str):
            token = value.strip()
            if ":" not in token:
                return
            if len(token) > 120:
                return
            if not _RESOURCE_CANDIDATE_CHARS.fullmatch(token):
                return
            lowered = token.lower()
            if _RESOURCE_IDENTIFIER_PATTERN.fullmatch(lowered):
                return
            context_label = f"{base_context}:{path}" if path else base_context
            logger.warning(
                "resource_identifier_invalid[%s]: %r",
                context_label,
                token,
            )

    visit(node, "")