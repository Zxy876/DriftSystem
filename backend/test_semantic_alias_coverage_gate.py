"""
【v1.18 数据测试】

测试目的：
- 确认语义别名覆盖率快照达到 ≥95% 阈值
- 校验 summary 指标与资源明细一致
"""

from __future__ import annotations

from tools.measure_semantic_alias_coverage import measure_alias_coverage
from tools.semantic_alias_coverage import load_snapshot


def test_semantic_alias_coverage_meets_threshold() -> None:
    report = measure_alias_coverage()
    snapshot = load_snapshot()

    assert report.safe_auto_total > 0
    assert snapshot.safe_auto_total == report.safe_auto_total
    assert snapshot.alias_covered == report.covered
    assert snapshot.alias_covered <= snapshot.safe_auto_total
    assert abs(snapshot.computed_ratio() - snapshot.coverage_ratio) <= 0.005
    assert abs(snapshot.computed_ratio() - report.coverage_ratio) <= 0.005
    assert report.coverage_ratio >= max(0.95, snapshot.threshold)
    assert not report.missing