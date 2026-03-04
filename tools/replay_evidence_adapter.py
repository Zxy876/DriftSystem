from __future__ import annotations

import hashlib
import json
from typing import Dict, List, Tuple


WorldState = Dict[Tuple[int, int, int], str]


def _stable_hash(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def apply_commands(commands: List[dict]) -> WorldState:
    world: WorldState = {}
    for cmd in commands:
        if not isinstance(cmd, dict):
            continue
        if cmd.get("op") != "setblock":
            continue
        x = cmd.get("x")
        y = cmd.get("y")
        z = cmd.get("z")
        block = cmd.get("block")
        if not isinstance(x, int) or not isinstance(y, int) or not isinstance(z, int):
            continue
        if not isinstance(block, str) or not block:
            continue
        world[(x, y, z)] = block
    return world


def capture_world_state_snapshot(commands: List[dict]) -> dict:
    world = apply_commands(commands)
    normalized = [
        {"x": x, "y": y, "z": z, "block": block}
        for (x, y, z), block in sorted(world.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2], kv[1]))
    ]
    return {
        "world_block_count": len(normalized),
        "world_state_hash": _stable_hash(normalized),
        "world_state_preview": normalized[:5],
    }
