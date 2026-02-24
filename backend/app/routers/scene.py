import time
import os
import socket
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field

from app.core.creation import CreationPatchTemplate, CreationPlan, ResourceCatalog
from app.core.minecraft.rcon_client import RconClient
from app.core.story.story_engine import story_engine
from app.services import creation_workflow

router = APIRouter(prefix="/scene", tags=["scene"])
_catalog = ResourceCatalog()
_REALIZE_STATUSES = {"ok", "needs_review", "blocked"}
_DOMAIN_HALF_SPAN = 256
_DOMAIN_MIN_Y = 0
_DOMAIN_MAX_Y = 320
_PERSONAL_DOMAIN_SPACING = 1000
_SHARED_DOMAIN = "S"
_SHARED_CENTER = {"x": 0, "y": 64, "z": 0}
_PLAYER_DOMAIN_INDEX: Dict[str, int] = {}
_NEXT_DOMAIN_INDEX = 1


class SceneRealizeResponse(BaseModel):
    status: Literal["ok", "needs_review", "blocked"]
    scene_id: Optional[str] = None
    mode: Optional[str] = None
    domain: Optional[str] = None
    domain_candidate: Optional[str] = None
    domain_overridden: bool = False
    domain_center: Optional[Dict[str, int]] = None
    plan_id: Optional[str] = None
    patch_id: Optional[str] = None
    selected_assets: List[Dict[str, Any]] = Field(default_factory=list)
    execution_mode: Optional[Literal["dry_run", "execute"]] = None
    execution: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    needs_review: List[Dict[str, Any]] = Field(default_factory=list)


class SceneExecuteReadinessResponse(BaseModel):
    allow_execute_flag: bool
    rcon_available: bool
    executor_ready: bool
    mode: Literal["shared", "personal"]
    policy_allow_execute: bool
    can_execute: bool
    reason: List[str] = Field(default_factory=list)


def _is_scene_only_payload(payload: Dict[str, Any]) -> List[str]:
    forbidden: List[str] = []
    if not isinstance(payload, dict):
        return ["payload_must_be_object"]
    if isinstance(payload.get("text"), str) and payload.get("text", "").strip():
        forbidden.append("text_input_forbidden")
    if "narrative" in payload:
        forbidden.append("narrative_input_forbidden")
    return forbidden


def _extract_required(payload: Dict[str, Any]) -> tuple[Optional[str], List[str]]:
    missing: List[str] = []
    scene_id = payload.get("scene_id")
    for key in ("scene_id", "player_id", "mode", "domain", "anchor", "assets"):
        if key not in payload:
            missing.append(f"missing_{key}")
    if payload.get("mode") not in {"shared", "personal"}:
        missing.append("invalid_mode")
    assets = payload.get("assets")
    if not isinstance(assets, list) or not assets:
        missing.append("assets_must_be_non_empty_list")
    player_id = payload.get("player_id")
    if not isinstance(player_id, str) or not player_id.strip():
        missing.append("invalid_player_id")
    return str(scene_id) if scene_id else None, missing


def _assign_personal_domain(player_id: str) -> tuple[str, Dict[str, int]]:
    global _NEXT_DOMAIN_INDEX
    if player_id not in _PLAYER_DOMAIN_INDEX:
        _PLAYER_DOMAIN_INDEX[player_id] = _NEXT_DOMAIN_INDEX
        _NEXT_DOMAIN_INDEX += 1
    index = _PLAYER_DOMAIN_INDEX[player_id]
    domain = f"P{index}"
    center = {"x": index * _PERSONAL_DOMAIN_SPACING, "y": 64, "z": 0}
    return domain, center


def _resolve_domain_binding(mode: str, player_id: str, candidate_domain: Optional[str]) -> tuple[str, Dict[str, int], bool]:
    candidate = (candidate_domain or "").strip().upper()
    if mode == "shared":
        return _SHARED_DOMAIN, dict(_SHARED_CENTER), candidate != _SHARED_DOMAIN

    domain, center = _assign_personal_domain(player_id)
    return domain, center, candidate != domain


def _coerce_anchor(raw: Any) -> Optional[Dict[str, int]]:
    if not isinstance(raw, dict):
        return None
    try:
        return {
            "x": int(raw["x"]),
            "y": int(raw["y"]),
            "z": int(raw["z"]),
        }
    except (KeyError, TypeError, ValueError):
        return None


def _parse_bbox(tags: List[str]) -> tuple[int, int, int]:
    for tag in tags:
        if isinstance(tag, str) and tag.startswith("bbox:"):
            payload = tag.split(":", 1)[1]
            try:
                bx, by, bz = payload.split("x")
                return max(int(bx), 1), max(int(by), 1), max(int(bz), 1)
            except (ValueError, TypeError):
                continue
    return 1, 1, 1


def _span_bounds(anchor: Dict[str, int], bbox: tuple[int, int, int]) -> Dict[str, int]:
    span_x, span_y, span_z = bbox
    x_min = anchor["x"] - ((span_x - 1) // 2)
    x_max = x_min + span_x - 1
    y_min = anchor["y"]
    y_max = y_min + span_y - 1
    z_min = anchor["z"] - ((span_z - 1) // 2)
    z_max = z_min + span_z - 1
    return {
        "x_min": x_min,
        "x_max": x_max,
        "y_min": y_min,
        "y_max": y_max,
        "z_min": z_min,
        "z_max": z_max,
    }


def _domain_bounds(center: Dict[str, int]) -> Dict[str, int]:
    return {
        "x_min": center["x"] - _DOMAIN_HALF_SPAN,
        "x_max": center["x"] + _DOMAIN_HALF_SPAN,
        "y_min": _DOMAIN_MIN_Y,
        "y_max": _DOMAIN_MAX_Y,
        "z_min": center["z"] - _DOMAIN_HALF_SPAN,
        "z_max": center["z"] + _DOMAIN_HALF_SPAN,
    }


def _inside_domain(bounds: Dict[str, int], domain: Dict[str, int]) -> bool:
    return (
        bounds["x_min"] >= domain["x_min"]
        and bounds["x_max"] <= domain["x_max"]
        and bounds["y_min"] >= domain["y_min"]
        and bounds["y_max"] <= domain["y_max"]
        and bounds["z_min"] >= domain["z_min"]
        and bounds["z_max"] <= domain["z_max"]
    )


def _resolve_execution_mode(payload: Dict[str, Any]) -> tuple[Optional[str], List[str]]:
    if payload.get("execute") is True:
        return "execute", []

    raw = payload.get("execution_mode", "dry_run")
    if not isinstance(raw, str):
        return None, ["invalid_execution_mode"]

    mode = raw.strip().lower()
    if mode not in {"dry_run", "execute"}:
        return None, ["invalid_execution_mode"]
    return mode, []


def _execute_mode_enabled() -> bool:
    return str(os.environ.get("DRIFT_SCENE_REALIZE_ALLOW_EXECUTE", "0")).strip().lower() in {"1", "true", "yes", "on"}


def _rcon_available() -> bool:
    host = os.getenv("MINECRAFT_RCON_HOST", "127.0.0.1")
    try:
        port = int(os.getenv("MINECRAFT_RCON_PORT", "25575"))
    except ValueError:
        port = 25575
    password = os.getenv("MINECRAFT_RCON_PASSWORD", "drift_rcon_dev")
    try:
        timeout = float(os.getenv("MINECRAFT_RCON_TIMEOUT", "5.0"))
    except ValueError:
        timeout = 5.0

    client = RconClient(host=host, port=port, password=password, timeout=timeout)
    try:
        client.verify()
        return True
    except Exception:
        return False


def _build_scene_plan(scene_id: str, selected_assets: List[Dict[str, Any]]) -> CreationPlan:
    templates: List[CreationPatchTemplate] = []
    for item in selected_assets:
        resource_id = str(item.get("resource_id") or "unknown")
        idx = int(item.get("index", 0))
        commands = [cmd for cmd in item.get("commands", []) if isinstance(cmd, str) and cmd.strip()]
        template = CreationPatchTemplate(
            step_id=f"scene-{scene_id}-asset-{idx}",
            template_id=f"scene-{scene_id}-{idx}",
            status="resolved",
            summary=f"scene asset {resource_id}",
            step_type="scene_realization",
            world_patch={
                "mc": {"commands": commands},
                "metadata": {
                    "scene_id": scene_id,
                    "resource_id": resource_id,
                    "anchor": item.get("anchor"),
                },
            },
        )
        template.validation.execution_tier = "safe_auto"
        templates.append(template)

    return CreationPlan(
        action="scene_realize",
        materials=[],
        confidence=1.0,
        summary=f"Scene realization for {scene_id}",
        patch_templates=templates,
        notes=[],
        steps=[],
        execution_tier="safe_auto",
    )


@router.post("/realize", response_model=SceneRealizeResponse)
def realize_scene(payload: Dict[str, Any] = Body(...)):
    scene_id, structural_errors = _extract_required(payload)
    forbidden_errors = _is_scene_only_payload(payload)
    mode = str(payload.get("mode") or "").strip().lower()
    player_id = str(payload.get("player_id") or "").strip()
    domain_candidate = str(payload.get("domain") or "").strip().upper() or None
    execution_mode, execution_mode_errors = _resolve_execution_mode(payload)

    resolved_domain: Optional[str] = None
    domain_center: Optional[Dict[str, int]] = None
    domain_overridden = False
    if not structural_errors and mode in {"shared", "personal"} and player_id:
        resolved_domain, domain_center, domain_overridden = _resolve_domain_binding(
            mode,
            player_id,
            domain_candidate,
        )

    if structural_errors or forbidden_errors or execution_mode_errors:
        return SceneRealizeResponse(
            status="blocked",
            scene_id=scene_id,
            mode=mode or None,
            domain=resolved_domain,
            domain_candidate=domain_candidate,
            domain_overridden=domain_overridden,
            domain_center=domain_center,
            execution_mode=(execution_mode if execution_mode in {"dry_run", "execute"} else None),
            errors=structural_errors + forbidden_errors + execution_mode_errors,
        )

    domain_box = _domain_bounds(domain_center or dict(_SHARED_CENTER))
    scene_anchor = _coerce_anchor(payload.get("anchor"))
    if scene_anchor is None:
        return SceneRealizeResponse(
            status="blocked",
            scene_id=scene_id,
            mode=mode,
            domain=resolved_domain,
            domain_candidate=domain_candidate,
            domain_overridden=domain_overridden,
            domain_center=domain_center,
            execution_mode=execution_mode,
            errors=["invalid_scene_anchor"],
        )

    scene_bounds = _span_bounds(scene_anchor, (1, 1, 1))
    if not _inside_domain(scene_bounds, domain_box):
        return SceneRealizeResponse(
            status="blocked",
            scene_id=scene_id,
            mode=mode,
            domain=resolved_domain,
            domain_candidate=domain_candidate,
            domain_overridden=domain_overridden,
            domain_center=domain_center,
            execution_mode=execution_mode,
            errors=["scene_anchor_out_of_domain"],
        )

    assets = payload.get("assets") or []
    snapshot = _catalog.load_snapshot()
    record_map = {record.resource_id: record for record in snapshot.resources}

    selected_assets: List[Dict[str, Any]] = []
    review_items: List[Dict[str, Any]] = []
    for index, asset in enumerate(assets):
        if not isinstance(asset, dict):
            review_items.append({"index": index, "reason": "asset_must_be_object"})
            continue

        resource_id = str(asset.get("resource_id") or "").strip()
        if not resource_id:
            review_items.append({"index": index, "reason": "missing_resource_id"})
            continue

        record = record_map.get(resource_id)
        if record is None:
            review_items.append({"index": index, "resource_id": resource_id, "reason": "resource_not_found"})
            continue

        asset_anchor = _coerce_anchor(asset.get("anchor"))
        if asset_anchor is None:
            return SceneRealizeResponse(
                status="blocked",
                scene_id=scene_id,
                mode=mode,
                domain=resolved_domain,
                domain_candidate=domain_candidate,
                domain_overridden=domain_overridden,
                domain_center=domain_center,
                execution_mode=execution_mode,
                errors=[f"asset_{index}_invalid_anchor"],
            )

        bbox = _parse_bbox(record.tags)
        asset_bounds = _span_bounds(asset_anchor, bbox)
        if not _inside_domain(asset_bounds, domain_box):
            return SceneRealizeResponse(
                status="blocked",
                scene_id=scene_id,
                mode=mode,
                domain=resolved_domain,
                domain_candidate=domain_candidate,
                domain_overridden=domain_overridden,
                domain_center=domain_center,
                execution_mode=execution_mode,
                errors=[f"asset_{index}_out_of_domain"],
            )

        commands = [cmd for cmd in record.commands if isinstance(cmd, str) and cmd.strip()]
        if not commands:
            review_items.append({"index": index, "resource_id": resource_id, "reason": "empty_commands"})
            continue

        selected_assets.append(
            {
                "index": index,
                "resource_id": resource_id,
                "commands": list(commands),
                "anchor": asset_anchor,
                "bbox": {"x": bbox[0], "y": bbox[1], "z": bbox[2]},
            }
        )

    if review_items:
        return SceneRealizeResponse(
            status="needs_review",
            scene_id=scene_id,
            mode=mode,
            domain=resolved_domain,
            domain_candidate=domain_candidate,
            domain_overridden=domain_overridden,
            domain_center=domain_center,
            selected_assets=[],
            execution_mode=execution_mode,
            plan_id=None,
            patch_id=None,
            needs_review=review_items,
            errors=[],
        )

    if execution_mode == "execute" and not _execute_mode_enabled():
        return SceneRealizeResponse(
            status="blocked",
            scene_id=scene_id,
            mode=mode,
            domain=resolved_domain,
            domain_candidate=domain_candidate,
            domain_overridden=domain_overridden,
            domain_center=domain_center,
            selected_assets=[],
            execution_mode=execution_mode,
            plan_id=None,
            patch_id=None,
            needs_review=[],
            errors=["execute_mode_not_enabled"],
        )

    if execution_mode == "execute" and not creation_workflow.auto_execute_enabled():
        return SceneRealizeResponse(
            status="blocked",
            scene_id=scene_id,
            mode=mode,
            domain=resolved_domain,
            domain_candidate=domain_candidate,
            domain_overridden=domain_overridden,
            domain_center=domain_center,
            selected_assets=[],
            execution_mode=execution_mode,
            plan_id=None,
            patch_id=None,
            needs_review=[],
            errors=["execute_runtime_unavailable"],
        )

    token = f"scene-{int(time.time() * 1000)}"
    patch_id = f"{token}-patch"
    plan = _build_scene_plan(scene_id or "scene", selected_assets)

    execution_payload: Dict[str, Any]
    if execution_mode == "execute":
        report = creation_workflow.auto_execute_plan(plan, patch_id=patch_id)
        execution_payload = {
            "mode": "execute",
            "report": report.to_payload(),
        }
    else:
        dry_run_result = creation_workflow.dry_run_plan(plan, patch_id=patch_id)
        execution_payload = {
            "mode": "dry_run",
            "report": dry_run_result.to_payload(),
        }

    response = SceneRealizeResponse(
        status="ok",
        scene_id=scene_id,
        mode=mode,
        domain=resolved_domain,
        domain_candidate=domain_candidate,
        domain_overridden=domain_overridden,
        domain_center=domain_center,
        plan_id=f"{token}-plan",
        patch_id=patch_id,
        selected_assets=selected_assets,
        execution_mode=execution_mode,
        execution=execution_payload,
        needs_review=[],
        errors=[],
    )
    if response.status not in _REALIZE_STATUSES:
        raise HTTPException(status_code=500, detail="invalid_scene_realize_status")
    return response


@router.get("/execute-readiness", response_model=SceneExecuteReadinessResponse)
def scene_execute_readiness(player_id: Optional[str] = None):
    runtime_mode = story_engine.get_runtime_mode(player_id)
    mode: Literal["shared", "personal"] = "personal" if runtime_mode == story_engine.MODE_PERSONAL else "shared"
    policy_allow_execute = mode == "personal"

    allow_execute_flag = _execute_mode_enabled()
    rcon_available = _rcon_available()
    executor_ready = creation_workflow.auto_execute_enabled()

    reasons: List[str] = []
    if not allow_execute_flag:
        reasons.append("flag_disabled")
    if not rcon_available:
        reasons.append("rcon_unavailable")
    if not executor_ready:
        reasons.append("executor_unavailable")

    return SceneExecuteReadinessResponse(
        allow_execute_flag=allow_execute_flag,
        rcon_available=rcon_available,
        executor_ready=executor_ready,
        mode=mode,
        policy_allow_execute=policy_allow_execute,
        can_execute=allow_execute_flag and rcon_available and executor_ready,
        reason=reasons,
    )


@router.get("/test-rcon")
def test_rcon():
    s = socket.socket()
    s.settimeout(5)
    try:
        s.connect(("101.33.226.238", 25575))
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}
    finally:
        s.close()


@router.post("/prepare/{player_id}/{level_id}")
def prepare_scene(
    player_id: str,
    level_id: str,
    payload: Optional[Dict[str, Any]] = Body(default=None),
):
    """Return the staged scene bundle for a player entering a level."""

    try:
        return story_engine.prepare_scene_for_player(player_id, level_id)
    except FileNotFoundError as exc:  # pragma: no cover - surfaced as HTTP error
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/release/{player_id}/{scene_id}")
def release_scene(
    player_id: str,
    scene_id: str,
    payload: Optional[Dict[str, Any]] = Body(default=None),
):
    """Notify the backend that a player has left the scene."""

    reason = None
    if isinstance(payload, dict):
        raw_reason = payload.get("reason")
        if isinstance(raw_reason, str):
            reason = raw_reason

    return story_engine.release_scene_for_player(player_id, scene_id, reason)
