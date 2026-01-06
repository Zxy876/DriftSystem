"""Automated executor that turns queued build plans into actionable commands.

This module resolves mod hooks into explicit command lists, records execution
logs, and can optionally dispatch the resulting commands to a live server when
a command dispatcher (for example an RCON client) is configured.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .build_plan import BuildPlan, BuildPlanStatus
from .build_scheduler import BuildScheduler
from app.core.mods import ModManager


@dataclass
class ExecutionResult:
    plan_id: str
    summary: str
    status: BuildPlanStatus
    commands: List[str]
    log_path: Optional[Path]
    missing_mods: List[str] = field(default_factory=list)
    dispatched: bool = False
    dispatch_error: Optional[str] = None


class CommandLogWriter:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _prune_empty(self, value: object) -> Optional[object]:
        if value is None:
            return None
        if isinstance(value, dict):
            cleaned: Dict[str, object] = {}
            for key, raw in value.items():
                pruned = self._prune_empty(raw)
                if pruned is None:
                    continue
                cleaned[key] = pruned
            return cleaned or None
        if isinstance(value, list):
            cleaned_list: List[object] = []
            for item in value:
                pruned = self._prune_empty(item)
                if pruned is None:
                    continue
                cleaned_list.append(pruned)
            return cleaned_list or None
        return value

    def write(
        self,
        plan: BuildPlan,
        status: BuildPlanStatus,
        commands: List[str],
        extra: Optional[Dict[str, object]] = None,
    ) -> Path:
        payload: Dict[str, object] = {
            "plan_id": str(plan.plan_id),
            "summary": plan.summary,
            "status": status.value,
            "commands": commands,
            "mod_hooks": plan.mod_hooks,
            "steps": [
                {
                    "step_id": step.step_id,
                    "title": step.title,
                    "description": step.description,
                    "target_region": step.target_region,
                    "required_mod": step.required_mod,
                    "dependencies": step.dependencies,
                }
                for step in plan.steps
            ],
            "resource_ledger": plan.resource_ledger,
            "risk_notes": plan.risk_notes,
            "origin_scenario": plan.origin_scenario,
            "logged_at": datetime.now(timezone.utc).isoformat(),
        }
        if plan.player_pose is not None:
            payload["player_pose"] = plan.player_pose.model_dump(mode="json")
        if extra:
            payload["notes"] = extra
        payload = self._prune_empty(payload) or {}
        path = self.output_dir / f"{plan.plan_id}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path


class BuildExecutor:
    def __init__(
        self,
        scheduler: BuildScheduler,
        mod_manager: ModManager,
        log_writer: Optional[CommandLogWriter] = None,
        command_dispatcher: Optional[Callable[[List[str]], None]] = None,
    ) -> None:
        self._scheduler = scheduler
        self._mod_manager = mod_manager
        default_dir = scheduler.config.root_dir / "executed"
        self._log_writer = log_writer or CommandLogWriter(default_dir)
        self._command_dispatcher = command_dispatcher

    def process_all(self) -> List[ExecutionResult]:
        self._mod_manager.reload()
        results: List[ExecutionResult] = []
        while True:
            plan = self._scheduler.pop_next()
            if plan is None:
                break
            results.append(self._process_plan(plan))
        return results

    def _process_plan(self, plan: BuildPlan) -> ExecutionResult:
        plan.status = BuildPlanStatus.running
        missing_mods = [mod for mod in plan.mod_hooks if not self._mod_manager.has_mod(mod)]
        notes: Dict[str, object] = {}
        commands: List[str] = []
        fallback_mods: List[str] = []

        for mod_id in plan.mod_hooks:
            if mod_id in missing_mods:
                continue
            explicit = self._mod_manager.build_commands(mod_id)
            if explicit:
                for raw_command in explicit:
                    prepared = self._prepare_command(raw_command, plan)
                    if not prepared:
                        continue
                    if prepared not in commands:
                        commands.append(prepared)
                continue
            fallback = self._fallback_command(mod_id)
            if fallback:
                prepared = self._prepare_command(fallback, plan)
                if prepared and prepared not in commands:
                    commands.append(prepared)
                fallback_mods.append(mod_id)

        if fallback_mods:
            notes["fallback_mods"] = fallback_mods
        if missing_mods:
            notes["missing_mods"] = missing_mods

        if missing_mods:
            log_path = self._log_writer.write(plan, BuildPlanStatus.blocked, commands, notes)
            self._scheduler.archive(plan, folder="failed")
            return ExecutionResult(
                plan_id=str(plan.plan_id),
                summary=plan.summary,
                status=BuildPlanStatus.blocked,
                commands=commands,
                log_path=log_path,
                missing_mods=missing_mods,
            )

        if plan.mod_hooks and not commands:
            notes.setdefault("reason", "no build commands resolved")
            log_path = self._log_writer.write(plan, BuildPlanStatus.blocked, commands, notes)
            self._scheduler.archive(plan, folder="failed")
            return ExecutionResult(
                plan_id=str(plan.plan_id),
                summary=plan.summary,
                status=BuildPlanStatus.blocked,
                commands=commands,
                log_path=log_path,
                missing_mods=missing_mods,
            )

        dispatch_error: Optional[str] = None
        dispatched = False
        if commands and self._command_dispatcher:
            try:
                self._command_dispatcher(commands)
                dispatched = True
            except Exception as exc:  # pragma: no cover - defensive logging branch
                dispatch_error = str(exc)
                notes.setdefault("dispatch_error", dispatch_error)

        status = BuildPlanStatus.completed if dispatch_error is None else BuildPlanStatus.blocked
        log_path = self._log_writer.write(plan, status, commands, notes if notes else None)
        archive_folder = "completed" if status == BuildPlanStatus.completed else "failed"
        self._scheduler.archive(plan, folder=archive_folder)
        return ExecutionResult(
            plan_id=str(plan.plan_id),
            summary=plan.summary,
            status=status,
            commands=commands,
            log_path=log_path,
            missing_mods=missing_mods,
            dispatched=dispatched,
            dispatch_error=dispatch_error,
        )

    def _fallback_command(self, mod_id: str) -> Optional[str]:
        if ":" not in mod_id:
            return None
        namespace, identifier = mod_id.split(":", 1)
        datapack_ns = f"{namespace}_{identifier.replace('.', '_')}"
        command = f"function {datapack_ns}:init"
        record = self._mod_manager.get_mod(mod_id)
        if not record or not record.manifest.root_path:
            return command
        base = record.manifest.root_path / "data" / datapack_ns
        for folder in ("function", "functions"):
            candidate = base / folder / "init.mcfunction"
            if candidate.exists():
                return command
        return None

    def _prepare_command(self, raw_command: str, plan: BuildPlan) -> Optional[str]:
        if not raw_command:
            return None
        command = raw_command.strip()
        if not command:
            return None
        command = self._apply_pose_placeholders(command, plan)
        if not command:
            return None
        return command

    def _apply_pose_placeholders(self, command: str, plan: BuildPlan) -> Optional[str]:
        pose = plan.player_pose
        tokens = (
            "{world}",
            "{x}",
            "{y}",
            "{z}",
            "{x_f}",
            "{y_f}",
            "{z_f}",
            "{yaw}",
            "{pitch}",
        )
        if not any(token in command for token in tokens):
            return command
        if pose is None:
            return None
        replacements = {
            "{world}": pose.world,
            "{x}": str(int(round(pose.x))),
            "{y}": str(int(round(pose.y))),
            "{z}": str(int(round(pose.z))),
            "{x_f}": f"{pose.x:.2f}",
            "{y_f}": f"{pose.y:.2f}",
            "{z_f}": f"{pose.z:.2f}",
            "{yaw}": f"{pose.yaw:.2f}",
            "{pitch}": f"{pose.pitch:.2f}",
        }
        forward_matches = list(re.finditer(r"\{forward_([xyz])_(-?\d+(?:\.\d+)?)_?(f)?\}", command))
        if forward_matches:
            yaw_rad = math.radians(pose.yaw)
            cos_yaw = math.cos(yaw_rad)
            sin_yaw = math.sin(yaw_rad)
            for match in forward_matches:
                axis = match.group(1)
                distance = float(match.group(2))
                float_flag = match.group(3) is not None
                if axis == "x":
                    value = pose.x - sin_yaw * distance
                elif axis == "z":
                    value = pose.z + cos_yaw * distance
                else:  # 'y'
                    value = pose.y
                formatted = f"{value:.2f}" if float_flag else str(int(round(value)))
                replacements[match.group(0)] = formatted
        result = command
        for token, value in replacements.items():
            result = result.replace(token, value)
        return result