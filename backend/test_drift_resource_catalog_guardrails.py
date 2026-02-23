from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
SEED_CATALOG_PATH = ROOT / "data" / "transformer" / "resource_catalog.seed.json"
RUNTIME_CATALOG_PATH = ROOT / "data" / "transformer" / "resource_catalog.json"

EXPECTED_DRIFT_RESOURCE_IDS = {
    "drift:room_basic_7x5x7",
    "drift:room_small_5x4x5",
    "drift:path_axis_1x1x15",
    "drift:path_axis_3x1x15",
    "drift:open_field_15x1x15",
    "drift:open_field_9x1x9",
    "drift:npc_anchor_villager",
    "drift:animal_pair_sheep",
    "drift:event_marker_pressure_plate",
    "drift:event_marker_beacon",
}


def _load_json(path: Path) -> dict:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def _drift_resource_map(path: Path) -> dict[str, dict]:
    data = _load_json(path)
    resources = data.get("resources", [])
    return {
        item["resource_id"]: item
        for item in resources
        if isinstance(item, dict) and str(item.get("resource_id", "")).startswith("drift:")
    }


def _normalized_resource(resource: dict) -> dict:
    clone = dict(resource)
    for key in ("aliases", "tags"):
        values = clone.get(key)
        if isinstance(values, list):
            clone[key] = sorted(str(item) for item in values)
    return clone


def _parse_tilde_number(token: str) -> int:
    if token == "~":
        return 0
    if token.startswith("~"):
        suffix = token[1:]
        if suffix:
            return int(suffix)
    raise ValueError(f"Unsupported coordinate token: {token}")


def _extract_bbox_from_tags(resource: dict) -> tuple[int, int, int]:
    for tag in resource.get("tags", []):
        if isinstance(tag, str) and tag.startswith("bbox:"):
            payload = tag.split(":", 1)[1]
            x_str, y_str, z_str = payload.split("x")
            return int(x_str), int(y_str), int(z_str)
    raise AssertionError(f"Missing bbox tag on {resource.get('resource_id')}")


def _command_span(command: str) -> tuple[int, int, int]:
    tokens = command.split()
    if not tokens:
        raise AssertionError("Empty command")

    op = tokens[0]
    if op == "fill":
        if len(tokens) < 7:
            raise AssertionError(f"Invalid fill command: {command}")
        x1, y1, z1 = (_parse_tilde_number(tokens[1]), _parse_tilde_number(tokens[2]), _parse_tilde_number(tokens[3]))
        x2, y2, z2 = (_parse_tilde_number(tokens[4]), _parse_tilde_number(tokens[5]), _parse_tilde_number(tokens[6]))
        return abs(x2 - x1) + 1, abs(y2 - y1) + 1, abs(z2 - z1) + 1

    if op in {"setblock", "summon"}:
        if len(tokens) < 4:
            raise AssertionError(f"Invalid {op} command: {command}")
        return 1, 1, 1

    raise AssertionError(f"Unsupported command operator for drift guardrails: {op}")


def _resource_span(commands: list[str]) -> tuple[int, int, int]:
    x_max = y_max = z_max = 1
    for command in commands:
        sx, sy, sz = _command_span(command)
        x_max = max(x_max, sx)
        y_max = max(y_max, sy)
        z_max = max(z_max, sz)
    return x_max, y_max, z_max


def test_drift_resource_ids_are_exact_and_synced() -> None:
    seed_map = _drift_resource_map(SEED_CATALOG_PATH)
    runtime_map = _drift_resource_map(RUNTIME_CATALOG_PATH)

    assert set(seed_map.keys()) == EXPECTED_DRIFT_RESOURCE_IDS
    assert set(runtime_map.keys()) == EXPECTED_DRIFT_RESOURCE_IDS

    for resource_id in EXPECTED_DRIFT_RESOURCE_IDS:
        assert _normalized_resource(seed_map[resource_id]) == _normalized_resource(runtime_map[resource_id])


def test_drift_commands_follow_guardrails() -> None:
    runtime_map = _drift_resource_map(RUNTIME_CATALOG_PATH)

    for resource_id, resource in runtime_map.items():
        commands = resource.get("commands", [])
        assert isinstance(commands, list), f"{resource_id} commands must be a list"
        assert 1 <= len(commands) <= 6, f"{resource_id} commands count out of range: {len(commands)}"

        for command in commands:
            assert isinstance(command, str) and command.strip(), f"{resource_id} has empty command"
            lowered = command.lower()
            assert "function " not in lowered and not lowered.startswith("function"), (
                f"{resource_id} uses forbidden function command: {command}"
            )
            assert "~" in command, f"{resource_id} command must use relative coordinates: {command}"


def test_drift_bbox_matches_command_span() -> None:
    runtime_map = _drift_resource_map(RUNTIME_CATALOG_PATH)

    for resource_id, resource in runtime_map.items():
        bbox_x, bbox_y, bbox_z = _extract_bbox_from_tags(resource)
        span_x, span_y, span_z = _resource_span(resource.get("commands", []))

        assert span_x <= bbox_x, f"{resource_id} command span_x {span_x} exceeds bbox_x {bbox_x}"
        assert span_y <= bbox_y, f"{resource_id} command span_y {span_y} exceeds bbox_y {bbox_y}"
        assert span_z <= bbox_z, f"{resource_id} command span_z {span_z} exceeds bbox_z {bbox_z}"
