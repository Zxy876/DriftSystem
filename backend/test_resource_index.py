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

from app.ml.resource_index import ResourceIndex, ResourceIndexEntry


def test_resource_index_search_returns_sorted_results() -> None:
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

    results = index.search([0.6, 0.8], limit=2, min_score=0.1)

    assert [entry.resource_id for entry, _ in results] == ["minecraft:lantern", "minecraft:stone"]
    assert results[0][1] > results[1][1]