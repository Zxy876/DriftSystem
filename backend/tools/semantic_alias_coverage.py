"""
【v1.18 数据覆盖脚本】

模块用途：
- 本文件用于：加载语义别名覆盖率快照并执行量化校验，支撑 P3-1 的 ≥95% 指标

工程边界：
- 仅参与【数据统计 / 离线校验】
- ❌ 不具备执行权限
- ❌ 不得写入世界
- ❌ 不修改 ResourceCatalog

版本说明：
- 引入于 DriftSystem v1.18
- 属于“治理辅助层”，不属于“执行层”
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

DEFAULT_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "semantic_alias_coverage.yaml"


@dataclass(frozen=True)
class ResourceCoverage:
    """
    【为什么存在】
    - 抽象单个资源的覆盖信息，便于统计 safe_auto / 覆盖状态
    - 让离线脚本与测试共享一致的数据结构

    【它具体做什么】
    - 输入：资源的基础字段（resource_id、是否 safe_auto、覆盖状态）
    - 输出：提供 `is_safe_auto` 与 `is_covered` 判定接口
    - 被 CoverageSnapshot 统计函数调用

    【它明确不做什么】
    - 不负责读写磁盘
    - 不推断别名质量
    - 不进行任何执行裁决
    """

    resource_id: str
    is_safe_auto: bool
    status: str

    def is_covered(self) -> bool:
        """
        【为什么存在】
        - 判断当前资源是否满足“别名覆盖”要求

        【它具体做什么】
        - 当资源属于 safe_auto 且状态标记为 covered 时返回 True
        - 供 CoverageSnapshot 统计覆盖率

        【它明确不做什么】
        - 不验证别名内容
        - 不访问外部服务
        - 不修改任何状态
        """

        return self.is_safe_auto and self.status.lower().strip() == "covered"


@dataclass(frozen=True)
class CoverageSnapshot:
    """
    【为什么存在】
    - 统一封装别名覆盖率快照，便于校验与测试使用

    【它具体做什么】
    - 持有 summary 指标与资源明细
    - 暴露 `computed_ratio` 与 `validate` 方法供脚本与测试调用

    【它明确不做什么】
    - 不自动刷新数据
    - 不写回快照文件
    - 不决定 Feature Flag
    """

    safe_auto_total: int
    alias_covered: int
    coverage_ratio: float
    resources: Sequence[ResourceCoverage]
    threshold: float

    def computed_ratio(self) -> float:
        """
        【为什么存在】
        - 根据资源明细重新计算覆盖率，用于与 summary 对比

        【它具体做什么】
        - 返回 alias_covered / safe_auto_total，当 safe_auto_total 为 0 时返回 0.0

        【它明确不做什么】
        - 不写入 summary
        - 不触发外部统计
        - 不改写阈值
        """

        if self.safe_auto_total <= 0:
            return 0.0
        return self.alias_covered / self.safe_auto_total

    def covered_resources(self) -> Iterable[ResourceCoverage]:
        """
        【为什么存在】
        - 提供方便的 covered 资源迭代器供测试与脚本使用

        【它具体做什么】
        - 过滤出被标记为 covered 的 safe_auto 资源

        【它明确不做什么】
        - 不修改资源列表
        - 不推断额外信息
        - 不访问外部依赖
        """

        return (resource for resource in self.resources if resource.is_covered())

    def validate(self, *, threshold: float | None = None) -> None:
        """
        【为什么存在】
        - 在脚本或测试中执行一致的覆盖率校验逻辑

        【它具体做什么】
        - 校验输入数据总量是否匹配资源明细
        - 校验 summary 覆盖率与实际计算结果一致
        - 校验覆盖率是否达到阈值（默认使用 snapshot 中的 threshold 字段）

        【它明确不做什么】
        - 不尝试修复数据
        - 不修改阈值
        - 不替代更全面的仪表板
        """

        expected_threshold = threshold if threshold is not None else self.threshold
        if self.safe_auto_total <= 0:
            raise ValueError("semantic_alias_coverage_missing_safe_auto")

        safe_auto_count = sum(1 for resource in self.resources if resource.is_safe_auto)
        covered_count = sum(1 for resource in self.covered_resources())
        if safe_auto_count != self.safe_auto_total:
            raise ValueError(
                f"semantic_alias_coverage_mismatch_total expected={self.safe_auto_total} actual={safe_auto_count}"
            )
        if covered_count != self.alias_covered:
            raise ValueError(
                f"semantic_alias_coverage_mismatch_covered expected={self.alias_covered} actual={covered_count}"
            )

        computed = self.computed_ratio()
        if abs(computed - self.coverage_ratio) > 0.005:
            raise ValueError(
                f"semantic_alias_coverage_ratio_inconsistent expected={self.coverage_ratio:.4f} actual={computed:.4f}"
            )
        if computed < expected_threshold:
            raise ValueError(
                f"semantic_alias_coverage_below_threshold ratio={computed:.4f} threshold={expected_threshold:.4f}"
            )


def load_snapshot(path: Path = DEFAULT_FIXTURE_PATH) -> CoverageSnapshot:
    """
    【为什么存在】
    - 从磁盘加载别名覆盖快照供脚本与测试复用

    【它具体做什么】
    - 读取 JSON（YAML 兼容）文件并转化为 CoverageSnapshot
    - 自动回填阈值并执行基础校验

    【它明确不做什么】
    - 不生成新快照
    - 不写回数据
    - 不访问 ResourceCatalog
    """

    payload = json.loads(path.read_text(encoding="utf-8"))
    resources_raw = payload.get("resources") if isinstance(payload, dict) else []
    resources: list[ResourceCoverage] = []
    for item in resources_raw or []:
        if not isinstance(item, dict):
            continue
        resource_id = str(item.get("resource_id") or "").strip()
        if not resource_id:
            continue
        resources.append(
            ResourceCoverage(
                resource_id=resource_id,
                is_safe_auto=bool(item.get("is_safe_auto", False)),
                status=str(item.get("status") or "unknown"),
            )
        )

    summary = payload.get("summary") if isinstance(payload, dict) else {}
    safe_auto_total = int(summary.get("safe_auto_total") or 0)
    alias_covered = int(summary.get("alias_covered") or 0)
    coverage_ratio = float(summary.get("coverage_ratio") or 0.0)
    threshold = float(summary.get("threshold") or 0.95)

    snapshot = CoverageSnapshot(
        safe_auto_total=safe_auto_total,
        alias_covered=alias_covered,
        coverage_ratio=coverage_ratio,
        resources=tuple(resources),
        threshold=threshold,
    )
    snapshot.validate()
    return snapshot


if __name__ == "__main__":  # pragma: no cover - 手动运行入口
    snapshot = load_snapshot()
    print(
        json.dumps(
            {
                "safe_auto_total": snapshot.safe_auto_total,
                "alias_covered": snapshot.alias_covered,
                "coverage_ratio": round(snapshot.computed_ratio(), 4),
                "threshold": snapshot.threshold,
            },
            ensure_ascii=False,
        )
    )
