from app.core.ideal_city.device_spec import DeviceSpec
from app.core.ideal_city.scenario_repository import ScenarioContext
from app.core.ideal_city.story_state import StoryState
from app.core.ideal_city.story_state_agent import StoryStateAgent, StoryStateAgentContext
import app.core.ideal_city.story_state_agent as story_state_agent_module


def _build_context(*, narrative: str, location_hint: str | None = None) -> StoryStateAgentContext:
    spec = DeviceSpec(
        author_ref="tester",
        intent_summary="在社区入口搭建小型展台",
        scenario_id="default",
        raw_narrative="这是一段很长的关卡文本，但只应摘要后进入上下文。",
    )
    scenario = ScenarioContext(
        scenario_id="default",
        title="熄灯区公共工坊",
        problem_statement="夜间缺少可持续维护点",
        contextual_constraints=["夜间噪音限制"],
        stakeholders=["居民委员会"],
        emerging_risks=["维护断档"],
        success_markers=["连续一周稳定运行"],
    )
    state = StoryState(
        player_id="player-1",
        scenario_id="default",
        ready_for_build=True,
        location_hint=location_hint,
        notes=[
            "玩家确认继续推进展台讨论。",
            "社区希望先在入口附近观察人流。",
            "先做可回滚的轻量试部署。",
        ],
    )
    return StoryStateAgentContext(
        narrative=narrative,
        spec=spec,
        scenario=scenario,
        existing_state=state,
    )


def test_reunion_prompt_uses_runtime_container_context(monkeypatch):
    captured = {}

    monkeypatch.setattr(story_state_agent_module, "NARRATIVE_DENSITY", "low")

    def _fake_call_deepseek(context, messages, **kwargs):
        captured["context"] = context
        captured["messages"] = messages
        captured["kwargs"] = kwargs
        return {
            "parsed": {
                "logic_outline": ["步骤A", "步骤B", "步骤C"],
                "world_constraints": ["约束A", "约束B"],
                "resources": ["木材 - 社区", "照明 - 工坊", "绳索 - 志愿者"],
                "success_criteria": ["通过夜间巡检"],
                "risk_register": ["风险: 光照不足 / 增设临时灯"],
            }
        }

    monkeypatch.setattr(story_state_agent_module, "call_deepseek", _fake_call_deepseek)

    agent = StoryStateAgent()
    ctx = _build_context(narrative="继续，我们换到河边入口再推进。", location_hint="旧广场")
    patch = agent.infer(ctx)

    assert set(captured["context"].keys()) >= {
        "world_state",
        "active_scene",
        "player_input",
        "recent_history_summary",
    }
    assert "required_sections" not in captured["messages"][0]["content"]
    assert "WORLD_PROMPT_VERSION=reunion_v1" in captured["messages"][0]["content"]
    assert 600 <= int(captured["kwargs"]["max_tokens"]) <= 900

    assert patch.logic_outline is not None
    assert len(patch.logic_outline) <= 2


def test_reunion_prompt_non_push_keeps_minimal_extension(monkeypatch):
    monkeypatch.setattr(story_state_agent_module, "NARRATIVE_DENSITY", "low")

    def _fake_call_deepseek(context, messages, **kwargs):
        return {
            "parsed": {
                "logic_outline": ["A", "B", "C"],
                "resources": ["木材 - 社区", "照明 - 工坊", "绳索 - 志愿者"],
                "world_constraints": ["夜间噪音限制", "入口通行要留白"],
                "success_criteria": ["居民认可", "运行稳定"],
                "follow_up_questions": ["是否继续扩展？", "是否要补照明细节？"],
            }
        }

    monkeypatch.setattr(story_state_agent_module, "call_deepseek", _fake_call_deepseek)

    agent = StoryStateAgent()
    ctx = _build_context(narrative="我先看看。", location_hint="旧广场")
    patch = agent.infer(ctx)

    assert patch.logic_outline is not None and len(patch.logic_outline) == 1
    assert patch.resources is not None and len(patch.resources) == 1
    assert patch.follow_up_questions is not None and len(patch.follow_up_questions) == 1
