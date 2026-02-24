"""Instrumentation helpers for CityPhone endpoints.

Iteration 0 要求中提到“初始化指标采集”，因此提供最小实现：
- 若环境已经安装 `prometheus_client`，则导出标准 Counter 指标。
- 否则退化为本地计数器，供日志和调试时查询。

后续迭代可以在此基础上扩展摘要指标或统一接入现有监控系统。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

try:
    from prometheus_client import Counter
except ImportError:  # pragma: no cover - optional dependency
    Counter = None  # type: ignore


@dataclass
class _LocalCounter:
    value: float = 0.0

    def inc(self, amount: float = 1.0) -> None:
        self.value += amount

    def labels(self, **_: str) -> "_LocalCounter":  # mimic Prometheus API
        return self


if Counter is not None:  # pragma: no cover - exercised in production if available
    _STATE_COUNTER = Counter(
        "cityphone_state_requests_total",
        "Total number of CityPhone state requests served.",
    )
    _ACTION_COUNTER = Counter(
        "cityphone_action_requests_total",
        "Total number of CityPhone action submissions handled.",
    )
    _ACTION_ERROR_COUNTER = Counter(
        "cityphone_action_errors_total",
        "Total number of CityPhone action errors grouped by error code.",
        labelnames=("code",),
    )
    _SEMANTIC_REQUEST_COUNTER = Counter(
        "cityphone_semantic_candidate_requests_total",
        "Total number of semantic candidate evaluations grouped by flag state.",
        labelnames=("enabled",),
    )
    _SEMANTIC_CANDIDATE_COUNTER = Counter(
        "cityphone_semantic_candidates_total",
        "Total number of semantic candidates surfaced to CreationWorkflow.",
    )
    _SEMANTIC_LAYER_COUNTER = Counter(
        "cityphone_semantic_layer_candidates_total",
        "Total number of semantic-layer sourced candidates surfaced to CreationWorkflow.",
    )
else:
    _STATE_COUNTER = _LocalCounter()
    _ACTION_COUNTER = _LocalCounter()
    _ACTION_ERROR_COUNTER: Dict[str, _LocalCounter] = {}
    _SEMANTIC_REQUEST_COUNTER = _LocalCounter()
    _SEMANTIC_CANDIDATE_COUNTER = _LocalCounter()
    _SEMANTIC_LAYER_COUNTER = _LocalCounter()


def record_state_request() -> None:
    """Increment the state request counter."""

    _STATE_COUNTER.inc()


def record_action_request() -> None:
    """Increment the action request counter."""

    _ACTION_COUNTER.inc()


def record_action_error(code: Optional[str]) -> None:
    """Increment error counter for failed actions."""

    label = code or "unknown"
    if Counter is not None:  # pragma: no cover
        _ACTION_ERROR_COUNTER.labels(code=label).inc()
    else:
        bucket = _ACTION_ERROR_COUNTER.setdefault(label, _LocalCounter())
        bucket.inc()


def record_semantic_candidate_event(*, enabled: bool, total_candidates: int, semantic_layer_candidates: int) -> None:
    """
    【为什么存在】
    - 记录语义候选统计指标，补充 v1.18 语义层的可观测性
    - 为回滚演练与 Feature Flag 分析提供数据支撑

    【它具体做什么】
    - 输入：Feature Flag 是否开启、返回的候选数量、语义层产出的候选数量
    - 输出：无，更新 Prometheus 或本地计数器
    - 指标会被 CityPhone 仪表板与自检脚本读取

    【它明确不做什么】
    - 不做执行裁决
    - 不写入任何世界状态
    - 不改变语义候选的具体内容
    """

    enabled_label = "on" if enabled else "off"
    if Counter is not None:  # pragma: no cover - Prometheus path
        _SEMANTIC_REQUEST_COUNTER.labels(enabled=enabled_label).inc()
        _SEMANTIC_CANDIDATE_COUNTER.inc(max(total_candidates, 0))
        _SEMANTIC_LAYER_COUNTER.inc(max(semantic_layer_candidates, 0))
    else:
        _SEMANTIC_REQUEST_COUNTER.inc()
        _SEMANTIC_CANDIDATE_COUNTER.inc(max(total_candidates, 0))
        _SEMANTIC_LAYER_COUNTER.inc(max(semantic_layer_candidates, 0))


def get_local_snapshot() -> Dict[str, float]:
    """Expose local counter values when Prometheus is unavailable.

    Returns an empty dict when Prometheus counters are in use.
    """

    if Counter is not None:  # pragma: no cover
        return {}
    return {
        "state_requests": _STATE_COUNTER.value,
        "action_requests": _ACTION_COUNTER.value,
        "action_errors": {
            label: counter.value for label, counter in _ACTION_ERROR_COUNTER.items()
        },
        "semantic_requests": _SEMANTIC_REQUEST_COUNTER.value,
        "semantic_candidates_total": _SEMANTIC_CANDIDATE_COUNTER.value,
        "semantic_layer_candidates_total": _SEMANTIC_LAYER_COUNTER.value,
    }
