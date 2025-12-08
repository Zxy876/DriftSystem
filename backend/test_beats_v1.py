"""Regression test for StoryEngine beat progression (Phase 1).

Run with:

    cd backend
    source venv/bin/activate  # if available
    python test_beats_v1.py

The script loads level_03, feeds utterances that should sequentially
trigger each beat, and prints runtime snapshots alongside the returned
world patches.
"""

from __future__ import annotations

import json
from pprint import pprint

from app.core.story.story_engine import story_engine


def snapshot_runtime(player_id: str):
    runtime = story_engine.player_state[player_id].get("beat_runtime") or []
    compact = [
        {
            "id": entry.get("id"),
            "status": entry.get("status"),
            "fulfilled": list(entry.get("fulfilled_keys") or []),
            "requirements": list(entry.get("requirements_keys") or []),
        }
        for entry in runtime
    ]
    return compact


def main():
    player = "beat_test_regression"
    world = {"variables": {}}

    utterances = [
        "开始",
        "我害怕",
        "呐喊",
        "怎么办",
        "我觉得不太好玩",
        "我愿意",
        "愿谁记得谁",
    ]

    story_engine.player_state[player] = {"current_level": "level_03"}

    for text in utterances:
        node, patch, mc = story_engine.advance(player, world, {"say": text})
        print(f"=== 玩家说: {text}")
        print("node:")
        pprint(node, width=100)
        print("patch:")
        pprint(patch, width=100)
        print("runtime:")
        pprint(snapshot_runtime(player), width=120)
        print("exit_ready:", story_engine.player_state[player]["beat_state"].get("completed"))
        print("--")

    print("== 最终状态 ==")
    pprint(story_engine.player_state[player]["beat_state"])
    print("pending_events:")
    pprint(story_engine.player_state[player].get("pending_events"))


if __name__ == "__main__":
    main()