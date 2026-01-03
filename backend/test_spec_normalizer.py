"""Unit tests for SpecNormalizer heuristics."""

from app.core.ideal_city.pipeline import DeviceSpecSubmission
from app.core.ideal_city.scenario_repository import ScenarioContext
from app.core.ideal_city.spec_normalizer import SpecNormalizer


def test_normalizer_injects_defaults_without_ai():
    normalizer = SpecNormalizer()
    scenario = ScenarioContext(
        scenario_id="default",
        title="暮色集市",
        problem_statement="暮色时段摊主缺乏稳定的遮风避雨空间。",
        contextual_constraints=["夜间能源有限", "噪音需在居民可接受范围"],
        stakeholders=["暮色摊主联盟"],
        emerging_risks=["若照明维护缺失，安全隐患上升"],
        success_markers=["夜间摊位可持续运营", "居民投诉下降"],
    )
    submission = DeviceSpecSubmission(
        player_id="tester",
        narrative="我要在夜市搭建一个太阳能棚，解决摊主夜间摆摊的照明难题。",
        scenario_id="default",
    )

    normalized = normalizer.normalize(submission, scenario)

    assert "太阳能" in normalized.intent_summary
    for constraint in scenario.contextual_constraints:
        assert constraint in normalized.world_constraints
    assert len(normalized.logic_outline) >= 2
    assert normalized.logic_outline[0].startswith("目标：")
    assert normalized.logic_outline[1].startswith("执行：")
    assert normalized.success_criteria  # pulled from scenario defaults
    assert normalized.risk_register  # pulled from scenario defaults
    assert isinstance(normalized.resource_ledger, list)
