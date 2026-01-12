from common.protocols.story_state import coerce_story_state_patch


def test_coerce_story_state_patch_normalises_collections():
    raw = {
        "logic_outline": [" 先整理 ", "", None, "先整理"],
        "resources": ["木材 - 社区工坊", "木材 - 社区工坊", ""],
        "follow_up_questions": ["补充风险?", None],
        "coverage": {"logic_outline": 1, "risk_register": 0},
        "motivation_score": "120.5",
        "logic_score": 88,
        "build_capability": 96.0,
        "location_hint": " 熄灯区入口 ",
        "timestamp": " 2026-01-07T12:00:00Z ",
        "milestones": {
            "logic_from_npc": {
                "status": "COMPLETE",
                "source": " npc ",
                "note": " 完成对话",
            },
            "": {"status": "complete"},
            "invalid": "ignored",
        },
    }

    patch = coerce_story_state_patch(raw)

    assert patch["logic_outline"] == ["先整理"], "Duplicates and blanks should be removed"
    assert patch["resources"] == ["木材 - 社区工坊"], "Duplicate resources collapse"
    assert patch["follow_up_questions"] == ["补充风险?"], "Valid prompts are retained"
    assert patch["coverage"] == {"logic_outline": True, "risk_register": False}
    assert patch["motivation_score"] == 120
    assert patch["logic_score"] == 88
    assert patch["build_capability"] == 96
    assert patch["location_hint"] == "熄灯区入口"
    assert patch["timestamp"] == "2026-01-07T12:00:00Z"

    milestone = patch["milestones"]["logic_from_npc"]
    assert milestone["status"] == "complete"
    assert milestone["source"] == "npc"
    assert milestone["note"] == "完成对话"
    assert "invalid" not in patch["milestones"]


def test_coerce_story_state_patch_allows_sparse_payload():
    raw = {
        "notes": [],
        "milestones": {},
        "motivation_score": None,
        "blocking": ["缺少风险", "缺少风险"],
    }

    patch = coerce_story_state_patch(raw)

    assert patch["blocking"] == ["缺少风险"], "Deduplicated blocking entries remain"
    assert "notes" not in patch
    assert "milestones" not in patch
    assert "motivation_score" not in patch
