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

from typing import Dict

from app.ml.resource_index import ResourceIndex, ResourceIndexEntry
from app.ml.semantic_resolver import IndexedSemanticResolver
from app.ml import SemanticCandidate


class _StubEmbeddingModel:
    def __init__(self, mapping: Dict[str, tuple[float, float]]) -> None:
        self._mapping = mapping

    def embed(self, request) -> list[float]:
        vector = self._mapping.get(request.text.strip())
        if vector is None:
            return [0.0, 0.0]
        return list(vector)


def test_indexed_semantic_resolver_returns_candidates() -> None:
    entries = [
        ResourceIndexEntry(
            resource_id="minecraft:stone",
            display_name="Stone",
            aliases=("石头",),
            tags=("block",),
            embedding=(1.0, 0.0),
        ),
        ResourceIndexEntry(
            resource_id="minecraft:lantern",
            display_name="Lantern",
            aliases=("灯",),
            tags=("block",),
            embedding=(0.0, 1.0),
        ),
    ]
    index = ResourceIndex(
        model_name="semantic_index",
        model_version="semantic_index_test",
        generated_at="2026-01-20T00:00:00+00:00",
        entries=entries,
    )
    resolver = IndexedSemanticResolver(
        index=index,
        embedding_model=_StubEmbeddingModel({
            "stone": (1.0, 0.0),
            "place stone": (1.0, 0.0),
        }),
        min_confidence=0.1,
        per_query_limit=2,
    )

    candidates = resolver.propose(["stone"], "place stone", limit=2)

    assert candidates
    assert isinstance(candidates[0], SemanticCandidate)
    assert candidates[0].resource_id == "minecraft:stone"
    assert candidates[0].token in {"stone", "place stone"}
    assert candidates[0].origin == "semantic_index_test"
    assert "semantic_index" in candidates[0].sources