"""Shared helpers for chat-driven creation planning and execution."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, NamedTuple, Optional, Sequence, Tuple

from app.core.creation import (
    CreationPatchTemplate,
    CreationPlan,
    CreationPlanMaterial,
    CreationPlanResult,
    CreationPlanStep,
    PatchTemplateValidationResult,
    load_default_transformer,
)
from app.instrumentation import cityphone_metrics
from app.ml.embedding_model import EmbeddingModel
from app.ml.resource_index import ResourceIndex
from app.ml.semantic_resolver import IndexedSemanticResolver
from app.services.semantic_proposal import ResourceEntry, SemanticProposalService
from app.core.intent_creation import CreationIntentDecision, default_creation_classifier
from app.core.minecraft.rcon_client import RconClient
from app.core.world.patch_executor import PatchExecutionResult, PatchExecutor
from app.core.world.plan_executor import CommandRunner, PlanExecutor, PlanExecutionReport

logger = logging.getLogger("uvicorn.error")


class RconCommandRunner(CommandRunner):
    """Dispatch commands to the live Minecraft server via RCON."""

    def __init__(self, host: str, port: int, password: str, timeout: float) -> None:
        self._client = RconClient(host=host, port=port, password=password, timeout=timeout)
        self.enabled = False

    def run(self, commands: Iterable[str]) -> None:  # pragma: no cover - network side effect
        self._client.run(commands)

    def verify_connection(self) -> None:  # pragma: no cover - network side effect
        self._client.verify()
        self.enabled = True


_creation_classifier = default_creation_classifier()
_creation_transformer = load_default_transformer()
_patch_executor = PatchExecutor()


# 【语义层接入】确保 IndexedSemanticResolver 可以按需启用并随时回退
_SEMANTIC_INDEX_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "transformer" / "semantic_index.json"


@dataclass(frozen=True)
class _CatalogResourceEntry:
    resource_id: str
    display_name: str
    category: Optional[str]


_resource_entry_cache: Dict[str, _CatalogResourceEntry] = {}
_semantic_service_singleton: Optional[SemanticProposalService] = None


def _reset_semantic_layer_for_testing() -> None:
    """测试专用：重置语义层单例，避免跨用例污染。"""

    global _semantic_service_singleton
    _resource_entry_cache.clear()
    _semantic_service_singleton = None


def _env_flag(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _semantic_layer_enabled() -> bool:
    return _env_flag("SEMANTIC_LAYER_ENABLED", default=False)


def _transformer_proposal_enabled() -> bool:
    return _env_flag("TRANSFORMER_PROPOSAL_ENABLED", default=True)


def _build_semantic_resolver() -> Optional[IndexedSemanticResolver]:
    index_path_raw = os.getenv("SEMANTIC_INDEX_PATH")
    index_path = Path(index_path_raw) if index_path_raw else _SEMANTIC_INDEX_DEFAULT_PATH
    if not index_path.exists():
        logger.info("semantic_index_missing path=%s", index_path)
        return None
    try:
        index = ResourceIndex.load(index_path)
    except Exception:  # pragma: no cover - index 读取失败回退
        logger.exception("semantic_index_load_failed path=%s", index_path)
        return None

    min_confidence = max(0.0, min(1.0, _read_float("SEMANTIC_LAYER_MIN_CONFIDENCE", 0.35)))
    per_query_limit = max(1, _read_int("SEMANTIC_LAYER_PER_QUERY_LIMIT", 5))
    embedding_model = EmbeddingModel()
    return IndexedSemanticResolver(
        index=index,
        embedding_model=embedding_model,
        min_confidence=float(min_confidence),
        per_query_limit=int(per_query_limit),
        origin_label=index.model_version or "semantic_index",
    )


def _candidate_payload_builder(
    entry: ResourceEntry,
    *,
    source: str,
    confidence: Optional[float] = None,
    token: Optional[str] = None,
    reason: Optional[str] = None,
) -> Dict[str, object]:
    payload: Dict[str, object] = {
        "resource_id": entry.resource_id,
        "display_name": entry.display_name,
        "source": [source] if source else [],
    }
    if confidence is not None:
        payload["confidence"] = round(float(confidence), 3)
    if token is not None:
        payload["token"] = token
    if reason is not None:
        payload["reason"] = reason
    category = getattr(entry, "category", None)
    if isinstance(category, str) and category.strip():
        payload.setdefault("category", category.strip())
    return payload


def _resolve_catalog_entry(resource_id: str) -> Optional[ResourceEntry]:
    if not resource_id:
        return None
    cached = _resource_entry_cache.get(resource_id)
    if cached is not None:
        return cached
    snapshot = _creation_transformer.catalog.load_snapshot()
    for record in getattr(snapshot, "resources", []):
        if record.resource_id == resource_id:
            entry = _CatalogResourceEntry(
                resource_id=record.resource_id,
                display_name=record.label,
                category=getattr(record, "category", None),
            )
            _resource_entry_cache[resource_id] = entry
            return entry
    return None


def _iter_material_tokens(material_tokens: Sequence[str], message: Optional[str]) -> Iterable[str]:
    for token in material_tokens:
        if not isinstance(token, str):
            continue
        stripped = token.strip()
        if stripped:
            yield stripped


def _build_semantic_proposal_service() -> SemanticProposalService:
    try:
        resolver = _build_semantic_resolver()
    except Exception:  # pragma: no cover - 语义层初始化失败
        logger.exception("semantic_resolver_initialisation_failed")
        resolver = None

    return SemanticProposalService(
        transformer=_creation_transformer,
        transformer_feature_gate=_transformer_proposal_enabled,
        resource_resolver=_resolve_catalog_entry,
        candidate_builder=_candidate_payload_builder,
        token_iterator=_iter_material_tokens,
        semantic_resolver=resolver,
        semantic_feature_gate=_semantic_layer_enabled,
    )


def _get_semantic_proposal_service(force_refresh: bool = False) -> Optional[SemanticProposalService]:
    global _semantic_service_singleton
    if force_refresh or _semantic_service_singleton is None:
        try:
            _semantic_service_singleton = _build_semantic_proposal_service()
        except Exception:  # pragma: no cover - 初始化异常
            logger.exception("semantic_proposal_service_init_failed")
            _semantic_service_singleton = None
    return _semantic_service_singleton


def _material_tokens_from_decision(decision: CreationIntentDecision) -> List[str]:
    slots = getattr(decision, "slots", {})
    candidates = slots.get("materials", []) if isinstance(slots, dict) else []
    tokens: List[str] = []
    for token in candidates:
        if not isinstance(token, str):
            continue
        stripped = token.strip()
        if stripped:
            tokens.append(stripped)
    return tokens


def collect_semantic_candidates(
    decision: CreationIntentDecision,
    *,
    message: Optional[str],
    limit: int = 3,
) -> List[Dict[str, object]]:
    if not getattr(decision, "is_creation", False):
        return []
    flag_enabled = _semantic_layer_enabled()
    if limit <= 0:
        cityphone_metrics.record_semantic_candidate_event(
            enabled=flag_enabled,
            total_candidates=0,
            semantic_layer_candidates=0,
        )
        return []
    service = _get_semantic_proposal_service()
    if service is None:
        cityphone_metrics.record_semantic_candidate_event(
            enabled=flag_enabled,
            total_candidates=0,
            semantic_layer_candidates=0,
        )
        return []
    material_tokens = _material_tokens_from_decision(decision)
    # 【ML 角色声明】
    # ML_ROLE: 语义提议（proposal_only）
    # EXECUTION_AUTHORITY: 无
    # GOVERNANCE_OWNER: CreationWorkflow
    candidates = list(service.collect_candidates(material_tokens, message, limit=limit))
    semantic_hits = 0
    for candidate in candidates:
        sources = candidate.get("source") or candidate.get("sources") or []
        if isinstance(sources, (list, tuple, set)) and "semantic_layer" in {str(item) for item in sources}:
            semantic_hits += 1
    logger.info(
        "creation_semantic_candidates_collected",
        extra={
            "decision_is_creation": getattr(decision, "is_creation", False),
            "material_tokens": material_tokens,
            "total_candidates": len(candidates),
            "semantic_hits": semantic_hits,
        },
    )
    cityphone_metrics.record_semantic_candidate_event(
        enabled=flag_enabled,
        total_candidates=len(candidates),
        semantic_layer_candidates=semantic_hits,
    )
    return candidates

_BLOCK_ID_PATTERN = re.compile(r"minecraft:[a-z0-9_./\-]+", re.IGNORECASE)
_COORD_TRIPLE_PATTERN = re.compile(
    r"(?:坐标|坐標|coordinates?)\s*[:：]?\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_COORD_COMPONENT_PATTERN = re.compile(
    r"(?:(?:坐标)?\s*(x|y|z)\s*[:=]\s*(-?\d+(?:\.\d+)?))",
    re.IGNORECASE,
)


class BlockPlacement(NamedTuple):
    block_id: str
    x: int
    y: int
    z: int
    command: str


class HardRouteOutcome(NamedTuple):
    plan_result: CreationPlanResult
    report: PlanExecutionReport
    placement: BlockPlacement


class HardRouteUnavailableError(RuntimeError):
    """Raised when the hard creation route cannot execute commands."""


def _match_hard_route(message: Optional[str]) -> Optional[BlockPlacement]:
    if not message:
        return None

    block_match = _BLOCK_ID_PATTERN.search(message)
    if not block_match:
        return None
    try:
        block_id = _sanitize_block_id(block_match.group(0))
    except ValueError:
        return None

    coords: Optional[Tuple[int, int, int]] = None
    triple_match = _COORD_TRIPLE_PATTERN.search(message)
    if triple_match:
        try:
            coords = tuple(int(round(float(group))) for group in triple_match.groups())
        except (TypeError, ValueError):
            coords = None
    if coords is None:
        coords = _parse_coordinate_components(message)
    if coords is None:
        return None

    command = f"setblock {coords[0]} {coords[1]} {coords[2]} {block_id}"
    return BlockPlacement(block_id=block_id, x=coords[0], y=coords[1], z=coords[2], command=command)


def _build_hard_route_plan(placement: BlockPlacement) -> CreationPlan:
    command = placement.command
    material = CreationPlanMaterial(
        token=placement.block_id,
        resource_id=placement.block_id,
        label=placement.block_id,
        status="resolved",
        confidence=1.0,
        quantity=1,
        tags=["hard_route"],
    )
    step = CreationPlanStep(
        step_id="step-1",
        title="Hard route setblock",
        description="Execute setblock via creation_hard_route",
        status="resolved",
        step_type="block_command",
        commands=[command],
        required_resource=placement.block_id,
        tags=["hard_route"],
    )
    template = CreationPatchTemplate(
        step_id=step.step_id,
        template_id="hard_place_block",
        status="resolved",
        summary="Hard route setblock",
        step_type="block_placement",
        world_patch={
            "mc": {
                "commands": [command],
            },
            "metadata": {
                "mode": "creation_hard_route",
                "block_id": placement.block_id,
                "coordinates": {
                    "x": placement.x,
                    "y": placement.y,
                    "z": placement.z,
                },
            },
        },
        notes=["creation_hard_route"],
        tags=["hard_route"],
        validation=PatchTemplateValidationResult(
            errors=[],
            warnings=[],
            execution_tier="safe_auto",
            missing_fields=[],
            unsafe_placeholders=[],
        ),
    )
    plan = CreationPlan(
        action="place_block",
        materials=[material],
        confidence=1.0,
        summary=f"Hard route setblock {placement.block_id} @ {placement.x} {placement.y} {placement.z}",
        steps=[step],
        patch_templates=[template],
        notes=["creation_hard_route"],
        execution_tier="safe_auto",
        safety_assessment={
            "mode": "creation_hard_route",
            "world_damage_risk": "low",
            "reversibility": True,
            "requires_confirmation": False,
        },
    )
    return plan


def creation_hard_route(raw_text: str, *, patch_id: Optional[str] = None) -> HardRouteOutcome:
    placement = _match_hard_route(raw_text)
    if placement is None:
        raise ValueError("hard_route_match_failed")

    executor = _ensure_plan_executor()
    if executor is None:
        raise HardRouteUnavailableError("plan_executor_unavailable")

    plan = _build_hard_route_plan(placement)
    logger.info(
        "creation_hard_route executing setblock %s", placement.command,
    )
    logger.warning("[HardRoute] BEFORE auto_execute")
    report = executor.auto_execute(plan, patch_id=patch_id)
    logger.warning("[HardRoute] AFTER auto_execute report=%s", report.patch_id)
    return HardRouteOutcome(
        plan_result=CreationPlanResult(plan=plan, snapshot_generated_at=None),
        report=report,
        placement=placement,
    )


def try_creation_hard_route(raw_text: str, *, patch_id: Optional[str] = None) -> Optional[HardRouteOutcome]:
    try:
        return creation_hard_route(raw_text, patch_id=patch_id)
    except ValueError:
        return None



def _read_int(env: str, default: int) -> int:
    raw = os.getenv(env)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:  # pragma: no cover - defensive guard
        logger.warning("Invalid %s=%s; using %s", env, raw, default)
        return default


def _read_float(env: str, default: float) -> float:
    raw = os.getenv(env)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:  # pragma: no cover - defensive guard
        logger.warning("Invalid %s=%s; using %s", env, raw, default)
        return default


def _sanitize_block_id(block_id: str) -> str:
    candidate = (block_id or "").strip().lower()
    if not candidate:
        raise ValueError("empty_block_id")
    if not _BLOCK_ID_PATTERN.fullmatch(candidate):
        raise ValueError(f"invalid_block_id:{block_id}")
    return candidate


def _parse_setblock_command(command: str) -> Optional[BlockPlacement]:
    if not command:
        return None
    tokens = command.strip().split()
    if len(tokens) < 5 or tokens[0].lower() != "setblock":
        return None
    try:
        x = int(round(float(tokens[1])))
        y = int(round(float(tokens[2])))
        z = int(round(float(tokens[3])))
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive guard
        raise ValueError(f"invalid_setblock_coordinates:{command}") from exc
    block_id = _sanitize_block_id(tokens[4])
    return BlockPlacement(block_id=block_id, x=x, y=y, z=z, command=command.strip())


def _parse_coordinate_components(message: str) -> Optional[Tuple[int, int, int]]:
    components: Dict[str, float] = {}
    for match in _COORD_COMPONENT_PATTERN.finditer(message):
        axis = match.group(1).lower()
        value = match.group(2)
        try:
            components[axis] = float(value)
        except (TypeError, ValueError):  # pragma: no cover - defensive guard
            continue
    if {"x", "y", "z"}.issubset(components):
        return tuple(int(round(components[axis])) for axis in ("x", "y", "z"))
    return None


def _build_block_plan(
    block_id: str,
    coords: Tuple[int, int, int],
    *,
    confidence: float,
    source: str = "chat",
) -> CreationPlan:
    sanitized = _sanitize_block_id(block_id)
    command = f"setblock {coords[0]} {coords[1]} {coords[2]} {sanitized}"
    clamped_confidence = max(confidence, 0.75)

    material = CreationPlanMaterial(
        token=sanitized,
        resource_id=sanitized,
        label=sanitized,
        status="resolved",
        confidence=clamped_confidence,
        quantity=1,
        tags=["explicit_coordinate"],
    )
    step = CreationPlanStep(
        step_id="step-1",
        title=f"Set {sanitized} at {coords[0]} {coords[1]} {coords[2]}",
        description="根据玩家提供的坐标放置方块。",
        status="resolved",
        step_type="block_command",
        commands=[command],
        required_resource=sanitized,
        tags=["explicit_coordinate"],
    )
    template = CreationPatchTemplate(
        step_id=step.step_id,
        template_id="explicit:setblock",
        status="resolved",
        summary=step.title,
        step_type=step.step_type,
        world_patch={
            "mc": {"commands": [command]},
            "metadata": {
                "source": source,
                "coordinates": {"x": coords[0], "y": coords[1], "z": coords[2]},
                "block_id": sanitized,
            },
        },
        mod_hooks=[],
        requires_player_pose=False,
        notes=["聊天坐标直接生成 setblock 指令。"],
        tags=["explicit_coordinate"],
    )

    return CreationPlan(
        action="place_block",
        materials=[material],
        confidence=clamped_confidence,
        summary=f"Place {sanitized} at {coords[0]} {coords[1]} {coords[2]}",
        steps=[step],
        patch_templates=[template],
        notes=[f"source:{source}"],
        execution_tier="safe_auto",
        validation_errors=[],
        validation_warnings=[],
        missing_fields=[],
        unsafe_steps=[],
        safety_assessment={
            "world_damage_risk": "low",
            "reversibility": True,
            "requires_confirmation": False,
        },
    )


def _extract_block_placement(plan: CreationPlan) -> Optional[BlockPlacement]:
    if plan is None:
        return None
    for step in plan.steps or []:
        for command in step.commands or []:
            parsed = _parse_setblock_command(command)
            if parsed is not None:
                return parsed
    return None


def _extract_explicit_block_plan(
    decision: CreationIntentDecision,
    message: Optional[str],
) -> Optional[CreationPlanResult]:
    if not decision.is_creation or not message:
        return None

    block_id: Optional[str] = None
    material_tokens: Sequence[str] = tuple(
        decision.slots.get("materials", []) if isinstance(decision.slots, dict) else []
    )
    for token in material_tokens:
        candidate = str(token).strip().lower()
        if candidate.startswith("minecraft:"):
            block_id = candidate
            break

    if block_id is None:
        match = _BLOCK_ID_PATTERN.search(message)
        if match:
            block_id = match.group(0).lower()

    if block_id is None:
        return None

    coords: Optional[Tuple[int, int, int]] = None
    triple_match = _COORD_TRIPLE_PATTERN.search(message)
    if triple_match:
        try:
            coords = tuple(int(round(float(group))) for group in triple_match.groups())
        except (TypeError, ValueError):  # pragma: no cover - defensive guard
            coords = None
    if coords is None:
        coords = _parse_coordinate_components(message)

    if coords is None:
        return None

    plan = _build_block_plan(block_id, coords, confidence=decision.confidence, source="explicit_coordinates")
    return CreationPlanResult(plan=plan, snapshot_generated_at=None)


def _build_command_runner() -> Optional[CommandRunner]:
    disable_flag = os.getenv("DRIFT_CREATION_AUTO_EXEC", "1").strip().lower()
    if disable_flag in {"0", "false", "no", "off"}:
        logger.warning("Creation auto-execute disabled via DRIFT_CREATION_AUTO_EXEC")
        return None

    host = os.getenv("MINECRAFT_RCON_HOST", "127.0.0.1")
    port = _read_int("MINECRAFT_RCON_PORT", 25575)
    password = os.getenv("MINECRAFT_RCON_PASSWORD", "drift_rcon_dev")
    timeout = _read_float("MINECRAFT_RCON_TIMEOUT", 5.0)
    runner = RconCommandRunner(host=host, port=port, password=password, timeout=timeout)
    try:
        runner.verify_connection()
    except Exception as exc:  # pragma: no cover - depends on environment
        logger.error("Creation auto-execute disabled: RCON handshake failed (%s)", exc)
        return None

    logger.info("Creation auto-execute wired to RCON %s:%s", host, port)
    return runner


_command_runner: Optional[CommandRunner] = _build_command_runner()
_plan_executor: Optional[PlanExecutor] = (
    PlanExecutor(_patch_executor, _command_runner) if _command_runner is not None else None
)


def _ensure_plan_executor() -> Optional[PlanExecutor]:
    global _command_runner, _plan_executor
    if _plan_executor is None:
        if _command_runner is None:
            _command_runner = _build_command_runner()
        if _command_runner is not None:
            _plan_executor = PlanExecutor(_patch_executor, _command_runner)
    executor = _plan_executor
    logger.warning(
        "[HardRoute][DEBUG] plan_executor=%s command_runner=%s rcon_enabled=%s",
        executor,
        getattr(executor, "_command_runner", None) if executor else None,
        getattr(getattr(executor, "_command_runner", None), "enabled", None) if executor else None,
    )
    return executor


def classify_message(message: str) -> CreationIntentDecision:
    """Run the creation intent classifier for a chat message."""

    return _creation_classifier.classify(message)


def generate_plan(decision: CreationIntentDecision, *, message: Optional[str] = None) -> CreationPlanResult:
    """Transform a classifier decision into a structured creation plan."""

    explicit = _extract_explicit_block_plan(decision, message)
    if explicit is not None:
        plan_result = explicit
    else:
        plan_result = _creation_transformer.transform(decision)

    if getattr(decision, "is_creation", False):
        plan_result.semantic_candidates = collect_semantic_candidates(decision, message=message, limit=5)
    else:
        plan_result.semantic_candidates = []
    return plan_result


def dry_run_plan(plan: CreationPlan, *, patch_id: Optional[str] = None) -> PatchExecutionResult:
    """Validate a plan without executing commands."""

    return _patch_executor.dry_run(plan, patch_id=patch_id)


def auto_execute_plan(plan: CreationPlan, *, patch_id: Optional[str] = None) -> PlanExecutionReport:
    """Execute a plan via dry-run + command dispatch workflow."""

    executor = _ensure_plan_executor()
    if executor is None:
        dry_run = _patch_executor.dry_run(plan, patch_id=patch_id)
        return PlanExecutionReport(
            patch_id=dry_run.patch_id,
            dry_run=dry_run,
            execution_results=[],
            errors=list(dry_run.errors),
            warnings=list(dry_run.warnings),
        )

    return executor.auto_execute(plan, patch_id=patch_id)


def auto_execute_enabled() -> bool:
    return _ensure_plan_executor() is not None


def world_patch_from_report(report: PlanExecutionReport) -> Optional[Dict[str, object]]:
    """Convert a plan execution report into a world_patch payload."""

    if report is None:
        return None

    commands: list[str] = []
    for result in report.execution_results:
        commands.extend(cmd for cmd in result.commands if isinstance(cmd, str) and cmd.strip())

    if not commands:
        for executed in report.dry_run.executed:
            commands.extend(cmd for cmd in executed.commands if isinstance(cmd, str) and cmd.strip())

    commands = [cmd for cmd in commands if cmd]
    if not commands:
        return None

    templates: list[Dict[str, object]] = []
    if report.execution_results:
        for result in report.execution_results:
            entry: Dict[str, object] = {
                "template_id": result.template_id,
                "step_id": result.step_id,
                "status": result.status,
            }
            if result.transaction is not None:
                entry["transaction"] = {
                    "patch_id": result.transaction.patch_id,
                    "status": result.transaction.status,
                    "created_at": result.transaction.created_at,
                }
            templates.append(entry)
    else:
        for executed in report.dry_run.executed:
            templates.append(
                {
                    "template_id": executed.template_id,
                    "step_id": executed.step_id,
                    "status": "validated",
                }
            )

    metadata: Dict[str, object] = {
        "patch_id": report.patch_id,
        "mode": "auto_execute" if report.execution_results else "dry_run",
        "templates": templates,
    }

    return {
        "mc": {"commands": list(commands)},
        "metadata": metadata,
    }


__all__ = [
    "auto_execute_plan",
    "auto_execute_enabled",
    "collect_semantic_candidates",
    "creation_hard_route",
    "HardRouteOutcome",
    "HardRouteUnavailableError",
    "classify_message",
    "dry_run_plan",
    "generate_plan",
    "try_creation_hard_route",
    "world_patch_from_report",
]
