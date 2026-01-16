from app.core.world import PatchTransactionLog, analyze_commands


def test_command_safety_flags_disallowed_tokens(tmp_path) -> None:
    report = analyze_commands(["op PlayerName"])
    assert report.errors

    clean = analyze_commands(["setblock ~ ~ ~ minecraft:stone"])
    assert not clean.errors


def test_patch_transaction_log_roundtrip(tmp_path) -> None:
    log = PatchTransactionLog(root=tmp_path)
    log.record(
        patch_id="patch-1",
        template_id="minecraft:stone::default",
        step_id="step-1",
        commands=["setblock ~ ~ ~ minecraft:stone"],
        undo_patch={"commands": ["setblock ~ ~ ~ minecraft:air"]},
        status="applied",
        metadata={"player": "Tester"},
    )
    entries = log.load()
    assert len(entries) == 1
    entry = entries[0]
    assert entry.metadata["player"] == "Tester"
    assert entry.undo_patch["commands"][0].endswith("minecraft:air")
