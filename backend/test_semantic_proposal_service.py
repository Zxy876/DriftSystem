"""
【v1.18 语义层测试】

测试目的：
- 验证治理不变量是否被破坏
- 验证澄清是否正确触发

注意：
- 本测试不验证具体 Minecraft 官名
- 本测试不作为资源正确性的依据
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from app.ml import SemanticCandidate
from app.services.semantic_proposal import SemanticProposalService


def _builder(
    entry: ResourceEntry,
    *,
    source: str,
    confidence: Optional[float] = None,
    token: Optional[str] = None,
    reason: Optional[str] = None,
) -> Dict[str, object]:
    candidate: Dict[str, object] = {
        "resource_id": entry.resource_id,
        "display_name": entry.display_name,
        "source": [source] if source else [],
    }
    if confidence is not None:
        candidate["confidence"] = round(float(confidence), 3)
    if token is not None:
        candidate["token"] = token
    if reason is not None:
        candidate["reason"] = reason
    return candidate


class _RecordingSnapshot:
    def __init__(self, responses: Sequence[tuple]) -> None:
        self._responses = list(responses)
        self.calls: List[tuple] = []

    def find_candidates(self, token: str, *, limit: int) -> List[tuple]:
        self.calls.append((token, limit))
        return list(self._responses)


class _StubCatalog:
    def __init__(self, snapshot: _RecordingSnapshot) -> None:
        self._snapshot = snapshot
        self.load_calls = 0

    def load_snapshot(self) -> _RecordingSnapshot:
        self.load_calls += 1
        return self._snapshot


class _StubTransformer:
    def __init__(self, catalog: _StubCatalog) -> None:
        self.catalog = catalog


class _StubRecord:
    def __init__(self, resource_id: str, label: str, category: str = "block") -> None:
        self.resource_id = resource_id
        self.label = label
        self.category = category


class _StubSemanticResolver:
    model_version = "semantic_index_test"

    def propose(
        self,
        material_tokens: Sequence[str],
        message: Optional[str],
        *,
        limit: int = 3,
    ) -> Sequence[SemanticCandidate]:
        return (
            SemanticCandidate(
                resource_id="minecraft:stone",
                confidence=0.9,
                token=material_tokens[0] if material_tokens else "",
                origin="semantic_index_test",
                sources=("semantic_index",),
                reason=None,
            ),
        )


@dataclass
class _ResourceEntry:
    resource_id: str
    display_name: str


def test_collect_candidates_returns_empty_when_disabled() -> None:
    snapshot = _RecordingSnapshot([])
    catalog = _StubCatalog(snapshot)
    service = SemanticProposalService(
        transformer=_StubTransformer(catalog),
        transformer_feature_gate=lambda: False,
        resource_resolver=lambda resource_id: _ResourceEntry(resource_id=resource_id, display_name=resource_id),
        candidate_builder=_builder,
        token_iterator=lambda tokens, message: ["stone"],
    )

    result = service.collect_candidates(["stone"], "place stone", limit=3)

    assert result == []
    assert catalog.load_calls == 0
    assert snapshot.calls == []


def test_collect_candidates_applies_limit_and_structure() -> None:
    responses = [
        (_StubRecord("minecraft:stone", "Stone"), 0.9),
        (_StubRecord("minecraft:lantern", "Lantern", category="item"), 0.85),
        (_StubRecord("minecraft:sandstone", "Sandstone"), 0.6),
    ]
    snapshot = _RecordingSnapshot(responses)
    catalog = _StubCatalog(snapshot)
    entries = {
        "minecraft:stone": _ResourceEntry(resource_id="minecraft:stone", display_name="Stone"),
        "minecraft:sandstone": _ResourceEntry(resource_id="minecraft:sandstone", display_name="Sandstone"),
    }
    service = SemanticProposalService(
        transformer=_StubTransformer(catalog),
        transformer_feature_gate=lambda: True,
        resource_resolver=lambda resource_id: entries.get(resource_id),
        candidate_builder=_builder,
        token_iterator=lambda tokens, message: [" stone "],
    )

    result = service.collect_candidates(["stone"], "place stone", limit=2)

    assert [candidate["resource_id"] for candidate in result] == [
        "minecraft:stone",
        "minecraft:sandstone",
    ]
    assert result[0]["label"] == "Stone"
    assert result[0]["token"] == " stone "
    assert result[0]["source"] == ["transformer"]
    assert snapshot.calls == [("stone", 2)]
    assert catalog.load_calls == 1


def test_collect_candidates_merges_semantic_layer() -> None:
    entries = {
        "minecraft:stone": _ResourceEntry(resource_id="minecraft:stone", display_name="Stone"),
    }
    service = SemanticProposalService(
        transformer=_StubTransformer(_StubCatalog(_RecordingSnapshot([]))),
        transformer_feature_gate=lambda: False,
        resource_resolver=lambda resource_id: entries.get(resource_id),
        candidate_builder=_builder,
        token_iterator=lambda tokens, message: tokens,
        semantic_resolver=_StubSemanticResolver(),
        semantic_feature_gate=lambda: True,
    )

    result = service.collect_candidates(["stone"], "place stone", limit=2)

    assert result
    assert result[0]["resource_id"] == "minecraft:stone"
    assert "semantic_layer" in result[0]["source"]
    assert result[0]["origin"] == "semantic_index_test"
