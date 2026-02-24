"""
【v1.18 语义层测试】

测试目的：
- 验证 Feature Flag 关闭时退回 v1.17 行为
- 验证开启语义层后会调用 IndexedSemanticResolver
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Generator, List, Optional, Sequence

import pytest

from app.ml import SemanticCandidate
from app.services import creation_workflow


@dataclass
class _StubRecord:
    resource_id: str
    label: str
    category: str = "block"
    tags: Sequence[str] = ()


class _StubSnapshot:
    def __init__(self, records: Sequence[_StubRecord]) -> None:
        self.resources = list(records)
        self.calls: List[tuple[str, int]] = []

    def find_candidates(self, token: str, *, limit: int) -> List[tuple[_StubRecord, float]]:
        self.calls.append((token, limit))
        if not self.resources:
            return []
        return [(self.resources[0], 0.87)]


class _StubCatalog:
    def __init__(self, snapshot: _StubSnapshot) -> None:
        self._snapshot = snapshot

    def load_snapshot(self) -> _StubSnapshot:
        return self._snapshot


class _StubTransformer:
    def __init__(
        self,
        catalog: _StubCatalog,
        *,
        plan_factory: Optional[Callable[[object], creation_workflow.CreationPlanResult]] = None,
    ) -> None:
        self.catalog = catalog
        self._plan_factory = plan_factory

    def transform(self, decision: creation_workflow.CreationIntentDecision) -> creation_workflow.CreationPlanResult:
        if self._plan_factory is not None:
            return self._plan_factory(decision)
        plan = creation_workflow.CreationPlan(
            action="stub_plan",
            materials=[],
            confidence=getattr(decision, "confidence", 0.5),
            summary="stub plan",
        )
        return creation_workflow.CreationPlanResult(plan=plan, snapshot_generated_at="stub_snapshot")


class _StubSemanticResolver:
    model_version = "semantic_index_test"

    def __init__(self) -> None:
        self.calls = 0

    def propose(
        self,
        material_tokens: Sequence[str],
        message: str | None,
        *,
        limit: int = 3,
    ) -> Sequence[SemanticCandidate]:
        self.calls += 1
        token = material_tokens[0] if material_tokens else ""
        return (
            SemanticCandidate(
                resource_id="minecraft:soul_lantern",
                confidence=0.91,
                token=token,
                origin=self.model_version,
                sources=("semantic_index",),
                reason=None,
            ),
        )


@dataclass
class _StubDecision:
    tokens: Sequence[str]
    is_creation: bool = True
    confidence: float = 0.8

    @property
    def slots(self) -> Dict[str, Sequence[str]]:
        return {"materials": list(self.tokens)}


@pytest.fixture(autouse=True)
def _reset_semantic_layer_singletons() -> Generator[None, None, None]:
    creation_workflow._reset_semantic_layer_for_testing()
    yield
    creation_workflow._reset_semantic_layer_for_testing()


def test_semantic_layer_feature_gates(monkeypatch: pytest.MonkeyPatch) -> None:
    records = [_StubRecord(resource_id="minecraft:soul_lantern", label="灵魂灯笼")]
    snapshot = _StubSnapshot(records)
    catalog = _StubCatalog(snapshot)
    transformer = _StubTransformer(catalog)
    monkeypatch.setattr(creation_workflow, "_creation_transformer", transformer)
    monkeypatch.setattr(creation_workflow, "_resource_entry_cache", {}, raising=False)

    resolver = _StubSemanticResolver()
    monkeypatch.setattr(creation_workflow, "_build_semantic_resolver", lambda: resolver)

    decision = _StubDecision(tokens=["灵魂灯"])

    monkeypatch.setenv("TRANSFORMER_PROPOSAL_ENABLED", "1")
    monkeypatch.setenv("SEMANTIC_LAYER_ENABLED", "0")
    creation_workflow._reset_semantic_layer_for_testing()
    off_results = creation_workflow.collect_semantic_candidates(decision, message="放一个灵魂灯笼", limit=3)

    assert resolver.calls == 0
    assert off_results
    assert all("semantic_layer" not in candidate.get("source", []) for candidate in off_results)

    monkeypatch.setenv("SEMANTIC_LAYER_ENABLED", "1")
    monkeypatch.setenv("TRANSFORMER_PROPOSAL_ENABLED", "0")
    resolver.calls = 0
    creation_workflow._reset_semantic_layer_for_testing()
    on_results = creation_workflow.collect_semantic_candidates(decision, message="放一个灵魂灯笼", limit=3)

    assert resolver.calls == 1
    assert on_results
    assert any("semantic_layer" in candidate.get("source", []) for candidate in on_results)


@pytest.mark.parametrize(
    "semantic_flag,transformer_flag,expect_semantic,expect_transformer,expect_candidates",
    [
        ("0", "1", False, True, True),
        ("1", "0", True, False, True),
        ("0", "0", False, False, False),
        ("1", "1", True, True, True),
    ],
)
def test_generate_plan_semantic_candidates_follow_feature_flags(
    monkeypatch: pytest.MonkeyPatch,
    semantic_flag: str,
    transformer_flag: str,
    expect_semantic: bool,
    expect_transformer: bool,
    expect_candidates: bool,
) -> None:
    records = [_StubRecord(resource_id="minecraft:soul_lantern", label="灵魂灯笼")]
    snapshot = _StubSnapshot(records)
    catalog = _StubCatalog(snapshot)

    def _plan_factory(decision: object) -> creation_workflow.CreationPlanResult:
        plan = creation_workflow.CreationPlan(
            action="stub_plan",
            materials=[],
            confidence=getattr(decision, "confidence", 0.8),
            summary="stub semantic toggle",
        )
        return creation_workflow.CreationPlanResult(plan=plan, snapshot_generated_at="stub_snapshot")

    transformer = _StubTransformer(catalog, plan_factory=_plan_factory)
    monkeypatch.setattr(creation_workflow, "_creation_transformer", transformer)
    monkeypatch.setattr(creation_workflow, "_resource_entry_cache", {}, raising=False)

    resolver = _StubSemanticResolver()
    monkeypatch.setattr(creation_workflow, "_build_semantic_resolver", lambda: resolver)

    decision = _StubDecision(tokens=["灵魂灯"])

    monkeypatch.setenv("SEMANTIC_LAYER_ENABLED", semantic_flag)
    monkeypatch.setenv("TRANSFORMER_PROPOSAL_ENABLED", transformer_flag)
    creation_workflow._reset_semantic_layer_for_testing()

    result = creation_workflow.generate_plan(decision, message="放一个灵魂灯笼")

    sources_union: set[str] = set()
    for candidate in result.semantic_candidates:
        sources = candidate.get("source", [])
        if isinstance(sources, list):
            sources_union.update(str(item) for item in sources)

    if expect_candidates:
        assert result.semantic_candidates
    else:
        assert result.semantic_candidates == []

    if expect_semantic:
        assert "semantic_layer" in sources_union
        assert resolver.calls == 1
    else:
        assert "semantic_layer" not in sources_union
        assert resolver.calls == 0

    if expect_transformer:
        assert "transformer" in sources_union
        assert snapshot.calls  # transformer path touched
    else:
        assert "transformer" not in sources_union
        assert snapshot.calls == []


def test_collect_semantic_candidates_records_enabled_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    records = [_StubRecord(resource_id="minecraft:soul_lantern", label="灵魂灯笼")]
    snapshot = _StubSnapshot(records)
    catalog = _StubCatalog(snapshot)
    transformer = _StubTransformer(catalog)
    monkeypatch.setattr(creation_workflow, "_creation_transformer", transformer)
    monkeypatch.setattr(creation_workflow, "_resource_entry_cache", {}, raising=False)

    resolver = _StubSemanticResolver()
    monkeypatch.setattr(creation_workflow, "_build_semantic_resolver", lambda: resolver)

    recorded: List[Dict[str, object]] = []

    def _fake_record_semantic_event(**payload: object) -> None:
        recorded.append(dict(payload))

    monkeypatch.setattr(
        creation_workflow.cityphone_metrics,
        "record_semantic_candidate_event",
        _fake_record_semantic_event,
    )

    decision = _StubDecision(tokens=["灵魂灯"])

    monkeypatch.setenv("SEMANTIC_LAYER_ENABLED", "1")
    monkeypatch.setenv("TRANSFORMER_PROPOSAL_ENABLED", "0")
    creation_workflow._reset_semantic_layer_for_testing()
    semantic_results = creation_workflow.collect_semantic_candidates(
        decision,
        message="放一个灵魂灯笼",
        limit=5,
    )

    assert recorded
    first_event = recorded[-1]
    assert first_event["enabled"] is True
    assert first_event["semantic_layer_candidates"] == 1
    assert first_event["total_candidates"] == len(semantic_results) == 1

    recorded.clear()
    monkeypatch.setenv("SEMANTIC_LAYER_ENABLED", "0")
    monkeypatch.setenv("TRANSFORMER_PROPOSAL_ENABLED", "0")
    creation_workflow._reset_semantic_layer_for_testing()
    fallback_results = creation_workflow.collect_semantic_candidates(
        decision,
        message="放一个灵魂灯笼",
        limit=5,
    )

    assert fallback_results == []
    assert recorded
    last_event = recorded[-1]
    assert last_event["enabled"] is False
    assert last_event["total_candidates"] == 0
    assert last_event["semantic_layer_candidates"] == 0
