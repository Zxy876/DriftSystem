"""
【v1.18 数据覆盖度量脚本】

职责：
- 读取 safe_auto 分母清单与语义别名覆盖快照
- 计算覆盖率、缺失清单与阈值对比
- 输出人类可读摘要 + 机器可解析 JSON

使用：
    python3 tools/measure_semantic_alias_coverage.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

try:  # pragma: no cover - 兼容直接执行脚本
    from .semantic_alias_coverage import CoverageSnapshot, ResourceCoverage, load_snapshot
except ImportError:  # pragma: no cover
    # 当以 `python3 tools/measure_semantic_alias_coverage.py` 直接运行时使用
    from semantic_alias_coverage import CoverageSnapshot, ResourceCoverage, load_snapshot  # type: ignore

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SAFE_AUTO_FIXTURE = BACKEND_ROOT / "tests" / "fixtures" / "safe_auto_resources.yaml"
COVERAGE_FIXTURE = BACKEND_ROOT / "tests" / "fixtures" / "semantic_alias_coverage.yaml"


@dataclass(frozen=True)
class SafeAutoResource:
    resource_id: str
    display_name: str


@dataclass(frozen=True)
class CoverageReport:
    safe_auto_total: int
    covered: int
    coverage_ratio: float
    missing: tuple[str, ...]
    threshold: float
    snapshot: CoverageSnapshot

    def to_json(self) -> dict:
        return {
            "total_safe_auto": self.safe_auto_total,
            "covered": self.covered,
            "coverage": round(self.coverage_ratio, 3),
            "threshold": round(self.threshold, 3),
            "missing": list(self.missing),
        }


def load_safe_auto_resources(path: Path = SAFE_AUTO_FIXTURE) -> Sequence[SafeAutoResource]:
    if not path.exists():
        raise FileNotFoundError(f"safe_auto_fixture_missing: {path}")

    resources: list[SafeAutoResource] = []
    current_id: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("- resource_id:"):
            current_id = line.split(":", 1)[1].strip()
            resources.append(SafeAutoResource(resource_id=current_id, display_name=""))
            continue
        if line.startswith("display_name:") and resources:
            display_name = line.split(":", 1)[1].strip()
            last = resources[-1]
            resources[-1] = SafeAutoResource(resource_id=last.resource_id, display_name=display_name)
    return tuple(resources)


def _covered_resources(snapshot: CoverageSnapshot) -> Iterable[ResourceCoverage]:
    return snapshot.covered_resources()


def measure_alias_coverage(
    *,
    safe_auto_fixture: Path = SAFE_AUTO_FIXTURE,
    coverage_fixture: Path = COVERAGE_FIXTURE,
) -> CoverageReport:
    safe_auto_entries = load_safe_auto_resources(safe_auto_fixture)
    snapshot = load_snapshot(coverage_fixture)

    safe_auto_ids = {entry.resource_id for entry in safe_auto_entries}
    covered_ids = {resource.resource_id for resource in _covered_resources(snapshot)}
    covered_safe_auto = sorted(safe_auto_ids & covered_ids)
    missing_safe_auto = sorted(safe_auto_ids - covered_ids)

    total = len(safe_auto_ids)
    coverage_ratio = (len(covered_safe_auto) / total) if total else 0.0

    return CoverageReport(
        safe_auto_total=total,
        covered=len(covered_safe_auto),
        coverage_ratio=coverage_ratio,
        missing=tuple(missing_safe_auto),
        threshold=snapshot.threshold,
        snapshot=snapshot,
    )


def _print_human_summary(report: CoverageReport) -> None:
    coverage_pct = report.coverage_ratio * 100
    threshold_pct = report.threshold * 100
    print("【语义别名覆盖率报告】")
    print(f"safe_auto 总量: {report.safe_auto_total}")
    print(f"已覆盖: {report.covered} ({coverage_pct:.2f}% )")
    print(f"指标阈值: {threshold_pct:.2f}%")
    if report.missing:
        print("未覆盖资源清单:")
        for resource_id in report.missing:
            print(f"- {resource_id}")
    else:
        print("未覆盖资源清单: 无")


def main() -> None:
    report = measure_alias_coverage()
    _print_human_summary(report)
    print(json.dumps(report.to_json(), ensure_ascii=False))


if __name__ == "__main__":
    main()
