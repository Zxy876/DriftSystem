"""Tests for Ideal City worldview-aware adjudication."""

from __future__ import annotations

import json
import os
from pathlib import Path
from importlib import reload

import pytest

from app.core.ideal_city import scenario_repository as scenario_module
from app.core.ideal_city import worldview as worldview_module
from app.core.ideal_city.adjudication_contract import VerdictEnum
from app.core.ideal_city.pipeline import DeviceSpecSubmission, IdealCityPipeline


@pytest.fixture(autouse=True)
def ideal_city_data_root(tmp_path, monkeypatch):
    data_root = tmp_path / "ideal_city"
    data_root.mkdir()

    worldview = {
        "spirit_core": "发明是一种对真实社会问题的负责回应，而非效率竞赛。",
        "historical_context": {"touchstones": ["社会尚未工业化，机械与结构仍在摸索阶段"]},
        "player_role": {"identity": "社会请来的创造回应者"},
        "design_principles": ["先理解世界问题，再动手建造"],
        "forbidden_patterns": ["只追求效率或炫技而忽略社会后果"],
        "review_questions": ["你正在回应的具体社会问题是什么？"],
        "response_styles": {
            "affirm": ["工坊长老们认可此项发明的长期照应价值。"],
            "reject": ["城市档案员指出：缺少对社会矛盾的明晰描述，无法归档。"],
            "follow_up": [
                "请补全至少一条被确认的世界限制。",
                "请提交逐步验证逻辑的过程说明。",
            ],
        },
    }
    scenario = {
        "scenario_id": "default",
        "title": "熄灯区的公共工坊",
        "problem_statement": "熄灯区缺乏安全工坊空间，居民无法修缮工具。",
        "contextual_constraints": ["夜间能源供应有限，噪音需受限"],
        "stakeholders": ["熄灯区居民委员会"],
        "emerging_risks": ["若维护计划缺失，工坊或成为安全隐患"],
        "success_markers": ["居民按周使用工坊且不发生事故"],
    }

    (data_root / "worldview.json").write_text(
        json.dumps(worldview, ensure_ascii=False), encoding="utf-8"
    )
    scenarios_dir = data_root / "scenarios"
    scenarios_dir.mkdir()
    (scenarios_dir / "default.json").write_text(
        json.dumps(scenario, ensure_ascii=False), encoding="utf-8"
    )

    monkeypatch.setenv("IDEAL_CITY_DATA_ROOT", str(data_root))
    worldview_module._cached_worldview = None
    worldview_module._cached_path = None
    reload(scenario_module)
    yield
    monkeypatch.delenv("IDEAL_CITY_DATA_ROOT", raising=False)
    worldview_module._cached_worldview = None
    worldview_module._cached_path = None


def test_single_sentence_submission_auto_structures():
    pipeline = IdealCityPipeline()
    submission = DeviceSpecSubmission(
        player_id="tester",
        narrative="我要搭建一个工坊",
        scenario_id="default",
    )
    result = pipeline.submit(submission)
    body_text = "\n".join(result.notice.body)
    assert result.ruling.verdict == VerdictEnum.ACCEPT
    assert result.spec.world_constraints  # should auto-inject scenario constraints
    assert len(result.spec.logic_outline) >= 2
    assert "档案员" in body_text
    assert "Context cues:" in result.notice.body
    assert any(line.startswith(" ~ 世界精神") for line in result.notice.body)
    assert any("熄灯区" in line for line in result.notice.body)
    assert result.notice.guidance  # fallback guidance strings should exist
    assert result.narration is not None


def test_acceptance_mentions_affirmation():
    pipeline = IdealCityPipeline()
    submission = DeviceSpecSubmission(
        player_id="tester",
        narrative="我要搭建一个工坊",
        scenario_id="default",
        world_constraints=["遵守夜间能源限制"],
        logic_outline=["整理材料", "邀请邻里"],
        risk_register=["噪音扰民"],
        success_criteria=["居民按周排班使用"],
    )
    result = pipeline.submit(submission)
    assert result.ruling.verdict == VerdictEnum.ACCEPT
    assert any("工坊长老们认可" in line for line in result.notice.body)
    assert any(line.startswith(" ~ 世界精神") for line in result.notice.body)
    assert result.notice.build_plan is not None
    assert result.build_plan is not None
    assert result.build_plan.summary
    data_root = Path(os.environ["IDEAL_CITY_DATA_ROOT"])  # provided by fixture
    queue_file = data_root / "build_queue" / "build_queue.jsonl"
    assert queue_file.exists()
    queue_lines = queue_file.read_text(encoding="utf-8").strip().splitlines()
    assert queue_lines, "Build plan queue should contain the generated plan"


def test_mod_refresh_intent_triggers_reload(tmp_path, monkeypatch):
    mods_root = tmp_path / "mods"
    mods_root.mkdir()
    monkeypatch.setenv("IDEAL_CITY_MODS_ROOT", str(mods_root))
    pipeline = IdealCityPipeline()
    manifest_dir = mods_root / "idealcity.sample"
    manifest_dir.mkdir()
    manifest = {
        "mod_id": "idealcity:sample",
        "name": "Sample Mod",
        "version": "0.1.0",
        "assets": {
            "schematics": [],
            "structures": [],
            "scripts": [],
            "textures": [],
        },
    }
    (manifest_dir / "mod.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    submission = DeviceSpecSubmission(
        player_id="tester",
        narrative="请帮我刷新模组缓存",
        scenario_id="default",
    )
    result = pipeline.submit(submission)
    assert result.ruling.verdict == VerdictEnum.ACCEPT
    assert result.notice.broadcast is not None
    mods = pipeline.list_mods()
    assert any(entry.get("mod_id") == "idealcity:sample" for entry in mods)
    monkeypatch.delenv("IDEAL_CITY_MODS_ROOT", raising=False)


def test_missing_structure_falls_back_to_rule_based_reject(monkeypatch):
    monkeypatch.setenv("IDEAL_CITY_AI_DISABLE", "1")
    pipeline = IdealCityPipeline()
    submission = DeviceSpecSubmission(
        player_id="tester",
        narrative="我想建设一个社区中心",
        scenario_id="default",
        world_constraints=[],
        logic_outline=["只有一个想法"],
        risk_register=[],
    )
    result = pipeline.submit(submission)
    monkeypatch.delenv("IDEAL_CITY_AI_DISABLE", raising=False)
    assert result.ruling.verdict == VerdictEnum.REJECT
    body_text = "\n".join(result.notice.body)
    assert "缺少必要结构" in body_text
    assert any("档案员说明" in line for line in result.notice.body)


def test_draft_submission_requests_manual_review(monkeypatch):
    monkeypatch.setenv("IDEAL_CITY_AI_DISABLE", "1")
    pipeline = IdealCityPipeline()
    submission = DeviceSpecSubmission(
        player_id="tester",
        narrative="这是一份草稿，需要人工确认",
        scenario_id="default",
        is_draft=True,
        world_constraints=["遵守夜间能源限制"],
        logic_outline=["整理材料", "邀请邻里"],
        risk_register=["噪音扰民"],
        success_criteria=["居民按周排班使用"],
    )
    result = pipeline.submit(submission)
    monkeypatch.delenv("IDEAL_CITY_AI_DISABLE", raising=False)
    assert result.ruling.verdict == VerdictEnum.REVIEW_REQUIRED
    assert any("草稿" in line for line in result.notice.body)
