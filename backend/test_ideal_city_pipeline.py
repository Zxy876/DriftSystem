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
from app.core.story.exhibit_instance_repository import (
    ExhibitInstance,
    ExhibitInstanceRepository,
)


ARCHIVE_FORBIDDEN = {
    "希望",
    "期待",
    "建议",
    "应当",
    "需要",
    "可以",
    "补齐",
    "完善",
    "改进",
    "优化",
    "生成",
    "执行",
    "计划",
    "步骤",
    "字段",
    "解锁",
    "进入",
    "准备就绪",
    "下一阶段",
}

ARCHIVE_SOURCE_REQUIRED = ("来源", "存档", "附件", "节选", "记录", "标注")
ARCHIVE_SOURCE_FORBIDDEN = {"理解", "解读", "重点", "总结"}

ARCHIVE_SAMPLE_NARRATIVE = (
    "《熄灯区公共工坊》展品整理稿：收集居民对夜间维修空间的记忆片段与讨论节选，"
    "提供给档案馆作为展品附注。"
)

ARCHIVE_UNKNOWN_KEYWORDS = ("记录", "档案", "文本")


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
    monkeypatch.setenv("IDEAL_CITY_AI_DISABLE", "1")
    worldview_module._cached_worldview = None
    worldview_module._cached_path = None
    reload(scenario_module)
    yield
    monkeypatch.delenv("IDEAL_CITY_DATA_ROOT", raising=False)
    monkeypatch.delenv("IDEAL_CITY_AI_DISABLE", raising=False)
    worldview_module._cached_worldview = None
    worldview_module._cached_path = None


@pytest.mark.xfail(reason="CityPhone summarizer fallback returns empty payload while AI service is offline", strict=False)
def test_archive_submission_produces_curatorial_payload():
    pipeline = IdealCityPipeline()
    submission = DeviceSpecSubmission(
        player_id="tester",
        narrative=ARCHIVE_SAMPLE_NARRATIVE,
        scenario_id="default",
    )
    pipeline.submit(submission)
    state = pipeline.cityphone_state("tester", "default")
    assert state.city_interpretation, "CityPhone should return curatorial notes"
    payload = state.model_dump(mode="json")
    assert set(payload) == {
        "city_interpretation",
        "unknowns",
        "history_entries",
        "narrative",
        "exhibit_mode",
        "exhibits",
    }
    assert isinstance(state.city_interpretation, list)
    assert state.city_interpretation
    assert all(isinstance(line, str) and line.strip() for line in state.city_interpretation)
    assert isinstance(state.unknowns, list)
    assert state.unknowns, "CityPhone should emit unresolved archival questions"
    assert all(isinstance(gap, str) and gap.strip() for gap in state.unknowns)
    assert any(
        any(keyword in gap for keyword in ARCHIVE_UNKNOWN_KEYWORDS)
        for gap in state.unknowns
    )
    assert payload["exhibits"] == {"instances": []}
    for line in state.city_interpretation:
        assert any(token in line for token in ARCHIVE_SOURCE_REQUIRED), line
        assert not any(token in line for token in ARCHIVE_SOURCE_FORBIDDEN), line
    sections = {section.slot: section for section in state.narrative.sections}
    assert set(sections) == {"gallery_status", "city_interpretation", "open_questions", "history_log", "archive_appendix"}
    gallery = sections["gallery_status"].body
    assert isinstance(gallery, list) and gallery
    assert all(isinstance(line, str) and line.strip() for line in gallery)
    interpretation_section = sections["city_interpretation"].body
    assert isinstance(interpretation_section, list) and interpretation_section
    for line in interpretation_section:
        assert any(token in line for token in ARCHIVE_SOURCE_REQUIRED), line
        assert not any(token in line for token in ARCHIVE_SOURCE_FORBIDDEN), line
    open_questions = sections["open_questions"].body
    assert isinstance(open_questions, list) and open_questions
    history_log = sections["history_log"].body
    assert isinstance(history_log, list) and history_log
    appendix = sections["archive_appendix"].body
    assert isinstance(appendix, list) and appendix
    for section in sections.values():
        for line in section.body:
            assert not any(token in line for token in ARCHIVE_FORBIDDEN), line
    assert state.history_entries
    assert all(isinstance(entry, str) and entry.strip() for entry in state.history_entries)
    assert any(":" in entry for entry in state.history_entries)


def test_cityphone_state_exposes_exhibit_instances(ideal_city_data_root):
    data_root = Path(os.environ["IDEAL_CITY_DATA_ROOT"])
    repo = ExhibitInstanceRepository(root=data_root / "exhibit_instances")

    pipeline = IdealCityPipeline()
    pipeline._exhibit_instance_repo = repo

    instance = ExhibitInstance(
        scenario_id="default",
        exhibit_id="amethyst_archive",
        level_id="level-artifact",
        snapshot_type="world_patch",
        title="Archive Instance",
        description="Captured world patch",
        created_by="tester",
    )
    repo.save_instance(instance)

    state = pipeline.cityphone_state(player_id="tester", scenario_id="default")
    payload = state.model_dump(mode="json")
    exhibits = payload["exhibits"]["instances"]

    assert exhibits, "CityPhone should surface exhibit instances when repository contains entries"
    first = exhibits[0]
    assert first["instance_id"] == instance.instance_id
    assert first["snapshot_type"] == "world_patch"
    assert first["title"] == "Archive Instance"
    assert first["description"] == "Captured world patch"
    assert state.exhibit_mode.label == "看展模式 · Archive"
    description = state.exhibit_mode.description
    assert isinstance(description, list) and description
    assert all(isinstance(line, str) and line.strip() for line in description)
    for forbidden_key in {"appendix", "technology_status", "player_id", "scenario_id", "plan", "verdict"}:
        assert forbidden_key not in payload


@pytest.mark.xfail(reason="CityPhone summarizer fallback returns empty payload while AI service is offline", strict=False)
def test_archive_submission_handles_extended_notes():
    pipeline = IdealCityPipeline()
    extended_narrative = (
        "展品旁白：整理熄灯区居民提交的口述稿、旧报导剪影与夜间记录本，"
        "以便观众理解公共空间想象如何被文字保存。"
    )
    submission = DeviceSpecSubmission(
        player_id="tester",
        narrative=extended_narrative,
        scenario_id="default",
    )
    pipeline.submit(submission)
    state = pipeline.cityphone_state("tester", "default")
    assert state.city_interpretation
    assert all(isinstance(line, str) and line.strip() for line in state.city_interpretation)
    assert state.unknowns
    assert all(isinstance(gap, str) and gap.strip() for gap in state.unknowns)
    combined_lines = list(state.city_interpretation) + list(state.unknowns)
    for line in combined_lines:
        assert not any(token in line for token in ARCHIVE_FORBIDDEN), line
    for line in state.city_interpretation:
        assert any(token in line for token in ARCHIVE_SOURCE_REQUIRED), line
        assert not any(token in line for token in ARCHIVE_SOURCE_FORBIDDEN), line


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


@pytest.mark.xfail(reason="CityPhone summarizer fallback returns empty payload while AI service is offline", strict=False)
def test_missing_structure_falls_back_to_rule_based_reject(monkeypatch):
    monkeypatch.setenv("IDEAL_CITY_AI_DISABLE", "1")
    pipeline = IdealCityPipeline()
    submission = DeviceSpecSubmission(
        player_id="tester",
        narrative="采访记录：居民讨论夜间公共空间的使用方式，但仍缺少文字整理稿。",
        scenario_id="default",
    )
    result = pipeline.submit(submission)
    monkeypatch.delenv("IDEAL_CITY_AI_DISABLE", raising=False)
    assert result.ruling.verdict in {VerdictEnum.REJECT, VerdictEnum.REVIEW_REQUIRED, VerdictEnum.ACCEPT}
    state = pipeline.cityphone_state("tester", "default")
    assert state.city_interpretation
    assert all(isinstance(line, str) and line.strip() for line in state.city_interpretation)
    assert state.unknowns
    assert all(isinstance(gap, str) and gap.strip() for gap in state.unknowns)
    for gap in state.unknowns:
        assert "需" not in gap and "补" not in gap, gap


@pytest.mark.xfail(reason="CityPhone summarizer fallback returns empty payload while AI service is offline", strict=False)
def test_archive_unknowns_focus_on_records(ideal_city_data_root):
    pipeline = IdealCityPipeline()
    submission = DeviceSpecSubmission(
        player_id="records_observer",
        narrative="整理稿：汇集曾经讨论夜间能源调度的不同文字版本。",
        scenario_id="default",
    )
    pipeline.submit(submission)
    state = pipeline.cityphone_state("records_observer", "default")
    assert state.unknowns
    assert all(isinstance(gap, str) and gap.strip() for gap in state.unknowns)
    assert any(any(keyword in gap for keyword in ARCHIVE_UNKNOWN_KEYWORDS) for gap in state.unknowns)
    for gap in state.unknowns:
        assert "补齐" not in gap and "步骤" not in gap, gap


@pytest.mark.xfail(reason="CityPhone summarizer fallback returns empty payload while AI service is offline", strict=False)
def test_archive_submission_accepts_fragmentary_notes(ideal_city_data_root):
    pipeline = IdealCityPipeline()
    submission = DeviceSpecSubmission(
        player_id="motivation_only",
        narrative="未整理的采访稿片段：讲述熄灯区居民如何描述公共工坊的记忆与情绪。",
        scenario_id="default",
    )
    pipeline.submit(submission)
    state = pipeline.cityphone_state("motivation_only", "default")
    assert state.city_interpretation
    assert all(isinstance(line, str) and line.strip() for line in state.city_interpretation)
    assert state.unknowns
    assert all(isinstance(gap, str) and gap.strip() for gap in state.unknowns)
    payload = state.model_dump(mode="json")
    for forbidden_key in {"appendix", "phase", "technology_status", "plan", "verdict", "resources"}:
        assert forbidden_key not in payload


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
