"""HTTP endpoints for the Ideal City minimal pipeline.

Endpoints here expose the submission → adjudication → execution loop without
allowing presentation layers to bypass world authority or mutate world state
directly.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.ideal_city.pipeline import (
    CityPhoneAction,
    DeviceSpecSubmission,
    IdealCityPipeline,
)
from app.core.ideal_city.narrative_ingestion import NarrativeChatEvent

router = APIRouter(prefix="/ideal-city", tags=["IdealCity"])
_pipeline = IdealCityPipeline()


@router.post("/device-specs")
def submit_device_spec(payload: DeviceSpecSubmission):
    result = _pipeline.submit(payload)
    return {
        "status": "ok",
        "spec": result.spec.model_dump(),
        "ruling": result.ruling.model_dump(),
        "notice": result.notice.model_dump(),
        "guidance": [item.model_dump() for item in result.guidance],
        "build_plan": result.build_plan.model_dump() if result.build_plan else None,
        "narration": result.narration.model_dump() if result.narration else None,
        "scenario": {
            "scenario_id": result.scenario.scenario_id,
            "title": result.scenario.title,
            "problem_statement": result.scenario.problem_statement,
            "contextual_constraints": result.scenario.contextual_constraints,
            "stakeholders": result.scenario.stakeholders,
            "emerging_risks": result.scenario.emerging_risks,
            "success_markers": result.scenario.success_markers,
        },
    }


@router.get("/device-specs/{spec_id}")
def get_device_spec(spec_id: str):
    spec = _pipeline.fetch_spec(spec_id)
    if not spec:
        raise HTTPException(status_code=404, detail="DeviceSpec not found")
    ruling = _pipeline.fetch_ruling(spec_id)
    return {
        "status": "ok",
        "spec": spec.model_dump(),
        "ruling": ruling.model_dump() if ruling else None,
    }


@router.get("/players/{player_id}/latest-ruling")
def latest_ruling(player_id: str):
    data = _pipeline.latest_for_player(player_id)
    if not data:
        return {"status": "empty", "player_id": player_id}
    ruling, notice = data
    return {
        "status": "ok",
        "player_id": player_id,
        "ruling": ruling.model_dump(),
        "notice": notice.model_dump(),
        "build_plan": _pipeline.fetch_plan_by_notice(notice),
    }


@router.get("/mods")
def list_mods():
    return {"status": "ok", "mods": _pipeline.list_mods()}


@router.post("/mods/refresh")
def refresh_mods():
    _pipeline.refresh_mods()
    return {"status": "ok", "mods": _pipeline.list_mods()}


@router.get("/cityphone/state/{player_id}")
def cityphone_state(player_id: str, scenario_id: str = "default"):
    state = _pipeline.cityphone_state(player_id, scenario_id)
    return {"status": "ok", "state": state.model_dump(mode="json")}


@router.post("/cityphone/action")
def cityphone_action(payload: CityPhoneAction):
    result = _pipeline.handle_cityphone_action(payload)
    return result.model_dump(mode="json")


@router.post("/narrative/ingest")
def narrative_ingest(payload: NarrativeChatEvent):
    result = _pipeline.ingest_narrative_event(payload)
    return result.model_dump(mode="json")


@router.get("/build-plans/executed/{plan_id}")
def get_executed_plan(plan_id: str):
    record = _pipeline.fetch_executed_plan(plan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Executed build plan not found")
    return {"status": "ok", "plan": record.to_payload()}


@router.get("/social-feedback/atmosphere")
def social_feedback_atmosphere(limit: int = 5):
    atmosphere = _pipeline.social_atmosphere(limit=limit)
    return {"status": "ok", "atmosphere": atmosphere.model_dump(mode="json")}