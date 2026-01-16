from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent
PARENT_ROOT = BACKEND_ROOT.parent
for candidate in (str(BACKEND_ROOT), str(PARENT_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.core.ideal_city.narrative_ingestion import NarrativeChatEvent
from app.core.ideal_city.pipeline import IdealCityPipeline


DATA_SOURCE = Path(__file__).resolve().parent / "data" / "ideal_city"


def _bootstrap_data_root(tmp_path: Path) -> Path:
    data_root = tmp_path / "ideal_city"
    shutil.copytree(DATA_SOURCE, data_root, dirs_exist_ok=True)
    worldview_path = data_root / "worldview.json"
    assert worldview_path.exists(), f"missing worldview.json at {worldview_path}"
    return data_root


@pytest.mark.parametrize("message, expected_status", [
    (
        """愿景：在熄灯区搭建一个协作工坊
行动：建立共享工作台；制定安全守则
资源：木材十组；铁锭两组
地点：world x=120 y=65 z=-34
成功：一周内完成搭建并投入使用
风险：噪音扰民，资源被挪用""",
        {"accepted", "needs_review"},
    ),
    ("随便聊聊今晚的天气，没有计划", {"ignored", "rejected", "needs_review"}),
])
def test_narrative_ingest_pipeline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, message: str, expected_status: set[str]) -> None:
    data_root = _bootstrap_data_root(tmp_path)
    monkeypatch.setenv("IDEAL_CITY_DATA_ROOT", str(data_root))

    pipeline = IdealCityPipeline()

    event = NarrativeChatEvent(player_id="tester", message=message)
    result = pipeline.ingest_narrative_event(event)

    assert result.status in expected_status
    assert result.intent_analysis is not None
    assert isinstance(result.intent_analysis.get("is_creation"), bool)
    if result.status not in {"rejected", "ignored"}:
        assert result.submission is not None
        assert result.notice is not None
        assert result.ruling is not None
    else:
        assert result.submission is None
        assert result.notice is None
        assert result.ruling is None
