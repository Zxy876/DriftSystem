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
else:
    _STATE_COUNTER = _LocalCounter()
    _ACTION_COUNTER = _LocalCounter()
    _ACTION_ERROR_COUNTER: Dict[str, _LocalCounter] = {}


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
    }
