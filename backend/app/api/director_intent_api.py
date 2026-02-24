"""导演输入框 Intent 入口（v1.21）。

模块角色：接收导演输入框文本，解析为结构化 DirectorIntent 并路由到 LevelSession / TaskManager / Actor 控制。
不做什么：不解析自然语言、不生成 world patch、不调用 Mineflayer/RCON、不过度扩展权限。
"""
from __future__ import annotations

import os
import json
import subprocess
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Deque, Dict, Tuple, List

from fastapi import APIRouter, HTTPException, Response

from app.levels.level_session import ALLOWED_TRANSITIONS, LevelSessionStore
from app.schemas.director_intent import (
    ActorIntent,
    BuildIntent,
    DirectorInput,
    DirectorIntent,
    LevelIntent,
    TaskIntent,
)
from app.services.task_runtime.TaskManager import TaskManager

router = APIRouter(prefix="/director", tags=["DirectorIntent"])

LEVEL_SESSION_DB = Path(os.environ.get("DRIFT_LEVEL_SESSION_DB", "backend/data/levels/sessions.db"))
CREW_RUNS_DIR = Path(os.environ.get("DRIFT_CREW_RUNS_DIR", "backend/logs/crew_runs"))
BLUEPRINT_DIR = Path(os.environ.get("DRIFT_BLUEPRINT_DIR", "backend/data/crew_blueprints"))
BRIDGE_SCRIPT = Path(os.environ.get("DRIFT_BRIDGE_SCRIPT", "system/taskcrew/bridge.js"))
STATUS_DIR = Path(os.environ.get("DRIFT_CREW_STATUS_DIR", CREW_RUNS_DIR / "status"))
ACTOR_INTENT_LOG = Path(os.environ.get("DRIFT_ACTOR_INTENT_LOG", "backend/logs/actor_intents.jsonl"))
ACTOR_QUEUE: Deque[ActorIntent] = deque()

ALLOWED_ACTIONS = {"setblock", "clear", "travel", "npc_summon"}


def _record_actor_intent(intent: ActorIntent) -> None:
    ACTOR_QUEUE.append(intent)
    try:
        ACTOR_INTENT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with ACTOR_INTENT_LOG.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "ts": datetime.utcnow().isoformat() + "Z",
                        "actor_id": intent.actor_id,
                        "action": intent.action,
                        "payload": intent.payload,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    except Exception:  # noqa: BLE001
        # 日志落盘失败不应中断主流程
        pass


def _status_path(task_id: str) -> Path:
    return STATUS_DIR / f"{task_id}.json"


def _write_status(task_id: str, data: Dict[str, object]) -> None:
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    path = _status_path(task_id)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_status(task_id: str) -> Dict[str, object] | None:
    path = _status_path(task_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _load_blueprint(intent: BuildIntent) -> Dict[str, object]:
    blueprint_path = BLUEPRINT_DIR / f"{intent.blueprint_id}.json"
    if not blueprint_path.exists():
        raise HTTPException(status_code=400, detail=f"blueprint_not_found:{intent.blueprint_id}")
    data = json.loads(blueprint_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="invalid_blueprint_format")
    actions = data.get("actions")
    if not isinstance(actions, list) or not actions:
        raise HTTPException(status_code=400, detail="blueprint_actions_missing")
    _validate_actions(actions)
    return data


def _validate_actions(actions: List[Dict[str, object]]) -> None:
    for idx, action in enumerate(actions):
        if not isinstance(action, dict):
            raise HTTPException(status_code=400, detail=f"action_not_dict:{idx}")
        name = str(action.get("action", "")).lower()
        if name not in ALLOWED_ACTIONS:
            raise HTTPException(status_code=400, detail=f"unsupported_action:{name}")
        if name in {"setblock", "travel"} and not action.get("position"):
            raise HTTPException(status_code=400, detail=f"missing_position:{name}:{idx}")
        if name == "setblock" and not action.get("block"):
            raise HTTPException(status_code=400, detail=f"missing_block:{idx}")
        if name == "clear":
            region = action.get("region")
            if not region or not isinstance(region, list) or len(region) != 6:
                raise HTTPException(status_code=400, detail=f"invalid_region:{idx}")
        if name == "npc_summon":
            if not action.get("name"):
                raise HTTPException(status_code=400, detail=f"npc_name_required:{idx}")
            if not action.get("position") or not isinstance(action.get("position"), list) or len(action.get("position")) != 3:
                raise HTTPException(status_code=400, detail=f"missing_position:npc_summon:{idx}")


def _offset_actions(actions: List[Dict[str, object]], intent: BuildIntent) -> List[Dict[str, object]]:
    if intent.origin_x is None and intent.origin_y is None and intent.origin_z is None:
        return actions
    ox = intent.origin_x or 0.0
    oy = intent.origin_y or 0.0
    oz = intent.origin_z or 0.0
    shifted: List[Dict[str, object]] = []
    for action in actions:
        name = str(action.get("action", "")).lower()
        clone = dict(action)
        if name in {"setblock", "travel", "npc_summon"} and isinstance(action.get("position"), list) and len(action["position"]) == 3:
            px, py, pz = action["position"]
            clone["position"] = [px + ox, py + oy, pz + oz]
        if name == "clear" and isinstance(action.get("region"), list) and len(action["region"]) == 6:
            x1, y1, z1, x2, y2, z2 = action["region"]
            clone["region"] = [x1 + ox, y1 + oy, z1 + oz, x2 + ox, y2 + oy, z2 + oz]
        shifted.append(clone)
    return shifted


def _write_pending_task(intent: BuildIntent, task: Dict[str, object]) -> Path:
    pending_dir = CREW_RUNS_DIR / "pending"
    pending_dir.mkdir(parents=True, exist_ok=True)
    task_path = pending_dir / f"{intent.task_id}.json"
    task_path.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
    status = {
        "task_id": intent.task_id,
        "blueprint_id": intent.blueprint_id,
        "origin": {
            "x": intent.origin_x,
            "y": intent.origin_y,
            "z": intent.origin_z,
        },
        "status": "pending",
        "exit_code": None,
        "started_at": None,
        "ended_at": None,
        "dry_run": True,
        "last_step": None,
    }
    _write_status(intent.task_id, status)
    return task_path


def _execute_task(task_id: str, task_path: Path, blueprint_id: str, origin: Dict[str, object]) -> Dict[str, object]:
    if not task_path.exists():
        raise HTTPException(status_code=404, detail="task_not_found")
    BRIDGE_SCRIPT.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "node",
        str(BRIDGE_SCRIPT),
        "--mode",
        "apply",
        "--task-file",
        str(task_path),
    ]
    started_at = datetime.utcnow().isoformat() + "Z"
    status = _load_status(task_id) or {}
    status.update({
        "task_id": task_id,
        "blueprint_id": blueprint_id,
        "origin": origin,
        "status": "active",
        "exit_code": None,
        "started_at": started_at,
        "dry_run": False,
    })
    _write_status(task_id, status)

    log_dir = task_path.parent
    runtime_log = log_dir / "runtime.log"

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd(), check=False, timeout=240)
    except FileNotFoundError as exc:  # noqa: BLE001
        status.update({"status": "failed", "exit_code": -127, "ended_at": datetime.utcnow().isoformat() + "Z"})
        _write_status(task_id, status)
        raise HTTPException(status_code=500, detail="node_not_found") from exc
    except subprocess.TimeoutExpired as exc:  # noqa: BLE001
        status.update({"status": "failed", "exit_code": -1, "ended_at": datetime.utcnow().isoformat() + "Z"})
        _write_status(task_id, status)
        raise HTTPException(status_code=500, detail="bridge_timeout") from exc

    stdout_lines = result.stdout.splitlines()
    stderr_lines = result.stderr.splitlines()
    # 写入 runtime.log
    with runtime_log.open("a", encoding="utf-8") as fh:
        fh.write(f"[start] task_id={task_id} blueprint={blueprint_id} origin={origin} at {started_at}\n")
        for line in stdout_lines:
            fh.write(f"[stdout] {line}\n")
        for line in stderr_lines:
            fh.write(f"[stderr] {line}\n")
        fh.write(f"[end] code={result.returncode} at {datetime.utcnow().isoformat()+'Z'}\n")

    status.update({
        "status": "finished" if result.returncode == 0 else "failed",
        "exit_code": result.returncode,
        "ended_at": datetime.utcnow().isoformat() + "Z",
        "last_step": stdout_lines[-1] if stdout_lines else None,
    })
    _write_status(task_id, status)

    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=f"bridge_failed:{result.stderr.strip()}")

    return {
        "status": status["status"],
        "stdout": stdout_lines,
        "stderr": stderr_lines,
        "exit_code": result.returncode,
        "started_at": started_at,
        "ended_at": status["ended_at"],
    }


def _parse_tokens(raw_text: str) -> Tuple[str, Dict[str, str]]:
    parts = raw_text.strip().split()
    if not parts:
        raise ValueError("empty_input")
    intent_type = parts[0].lower()
    kv: Dict[str, str] = {}
    for token in parts[1:]:
        if "=" not in token:
            raise ValueError(f"invalid_token:{token}")
        key, value = token.split("=", 1)
        if not key or not value:
            raise ValueError(f"invalid_token:{token}")
        kv[key.lower()] = value
    return intent_type, kv


def parse_director_intent(raw_text: str) -> DirectorIntent:
    intent_type, kv = _parse_tokens(raw_text)

    if intent_type == "level":
        level_id = kv.get("level_id")
        target_state = kv.get("target_state")
        if not level_id or not target_state:
            raise ValueError("level_intent_requires_level_id_and_target_state")
        return LevelIntent(level_id=level_id, target_state=target_state.upper(), actor_id=kv.get("actor_id"))

    if intent_type == "task":
        required = ["task_id", "level_id", "summary", "assigned_to"]
        missing = [key for key in required if not kv.get(key)]
        if missing:
            raise ValueError(f"task_intent_missing:{','.join(missing)}")
        return TaskIntent(
            task_id=kv["task_id"],
            level_id=kv["level_id"],
            summary=kv["summary"],
            assigned_to=kv["assigned_to"],
        )

    if intent_type == "actor":
        required = ["actor_id", "action"]
        missing = [key for key in required if not kv.get(key)]
        if missing:
            raise ValueError(f"actor_intent_missing:{','.join(missing)}")
        payload = {k: v for k, v in kv.items() if k not in {"actor_id", "action"}}
        return ActorIntent(actor_id=kv["actor_id"], action=kv["action"], payload=payload)

    if intent_type == "build":
        required = ["task_id", "blueprint_id", "level_id"]
        missing = [key for key in required if not kv.get(key)]
        if missing:
            raise ValueError(f"build_intent_missing:{','.join(missing)}")
        return BuildIntent(
            task_id=kv["task_id"],
            blueprint_id=kv["blueprint_id"],
            level_id=kv["level_id"],
            assigned_to=kv.get("assigned_to", "crew_builder_01"),
            origin_x=float(kv["origin_x"]) if kv.get("origin_x") else None,
            origin_y=float(kv["origin_y"]) if kv.get("origin_y") else None,
            origin_z=float(kv["origin_z"]) if kv.get("origin_z") else None,
        )

    raise ValueError(f"unsupported_intent_type:{intent_type}")


@router.post("/intents")
async def handle_director_intent(payload: DirectorInput):
    try:
        intent = parse_director_intent(payload.raw_text)
    except ValueError as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if isinstance(intent, LevelIntent):
        store = LevelSessionStore(LEVEL_SESSION_DB)
        store.create_session(intent.level_id)
        current = store.get_state(intent.level_id) or "IMPORTED"
        expected = ALLOWED_TRANSITIONS.get(current)
        if expected != intent.target_state:
            raise HTTPException(status_code=400, detail=f"invalid_transition:{current}->{intent.target_state}")
        if payload.dry_run:
            return {
                "status": "dry_run",
                "routed_to": "level_session",
                "current_state": current,
                "next_state": intent.target_state,
            }
        new_state = store.advance(intent.level_id, intent.target_state, actor_id=intent.actor_id)
        return {"status": "ok", "routed_to": "level_session", "state": new_state}

    if isinstance(intent, TaskIntent):
        if payload.dry_run:
            return {
                "status": "dry_run",
                "routed_to": "task_manager",
                "task": intent.model_dump(),
            }
        manager = TaskManager(base_dir=CREW_RUNS_DIR)
        record = manager.create_task(
            {
                "task_id": intent.task_id,
                "level_id": intent.level_id,
                "assigned_to": intent.assigned_to,
                "summary": intent.summary,
            }
        )
        return {"status": "ok", "routed_to": "task_manager", "task": record.model_dump()}

    if isinstance(intent, ActorIntent):
        if not payload.dry_run:
            _record_actor_intent(intent)
        return {
            "status": "dry_run" if payload.dry_run else "accepted",
            "routed_to": "actor_controller",
            "message": "v1.21 minimal: intent recorded; actor controller to consume",
            "intent": intent.model_dump(),
        }

    if isinstance(intent, BuildIntent):
        blueprint = _load_blueprint(intent)
        actions = blueprint.get("actions", [])
        actions = _offset_actions(actions, intent)
        task = {
            "task_id": intent.task_id,
            "level_id": intent.level_id,
            "assigned_to": intent.assigned_to,
            "blueprint_id": intent.blueprint_id,
            "origin": {
                "x": intent.origin_x,
                "y": intent.origin_y,
                "z": intent.origin_z,
            },
            "actions": actions,
        }
        _validate_actions(actions)
        task_path = _write_pending_task(intent, task)
        return {
            "status": "dry_run",
            "routed_to": "build_queue",
            "task_file": str(task_path),
            "actions": len(actions),
            "message": "已生成待审批建造任务，需 /director apply build <task_id> 触发执行",
            "task": task,
        }

    raise HTTPException(status_code=400, detail="unknown_intent")


@router.get("/actor/next")
async def pop_actor_intent(actor_id: str | None = None):
    """弹出下一条演员控制指令。

    - actor_id 为空时返回队首；指定时仅返回匹配 actor。
    - 无可用指令时返回 204。
    """
    if not ACTOR_QUEUE:
        return Response(status_code=204)

    if actor_id is None:
        intent = ACTOR_QUEUE.popleft()
        return {"status": "ok", "intent": intent.model_dump()}

    # 线性扫描，数量极小（导演输入手动提交）
    for _ in range(len(ACTOR_QUEUE)):
        intent = ACTOR_QUEUE.popleft()
        if intent.actor_id == actor_id:
            return {"status": "ok", "intent": intent.model_dump()}
        ACTOR_QUEUE.append(intent)

    return Response(status_code=204)


@router.post("/build/apply")
async def apply_build(task_id: str):
    pending_path = CREW_RUNS_DIR / "pending" / f"{task_id}.json"
    if not pending_path.exists():
        raise HTTPException(status_code=404, detail="pending_task_not_found")

    # 复制到 active 目录，便于审计
    active_dir = CREW_RUNS_DIR / "active" / task_id
    active_dir.mkdir(parents=True, exist_ok=True)
    task_path = active_dir / "task.json"
    task_data = json.loads(pending_path.read_text(encoding="utf-8"))
    _validate_actions(task_data.get("actions", []))
    task_path.write_text(json.dumps(task_data, ensure_ascii=False, indent=2), encoding="utf-8")

    result = _execute_task(task_id, task_path, task_data.get("blueprint_id", ""), task_data.get("origin", {}))
    return {
        "status": result.get("status", "finished"),
        "routed_to": "bridge",
        "task_id": task_id,
        "blueprint_id": task_data.get("blueprint_id"),
        "origin": task_data.get("origin"),
        "stdout": result.get("stdout", []),
        "stderr": result.get("stderr", []),
        "exit_code": result.get("exit_code"),
        "started_at": result.get("started_at"),
        "ended_at": result.get("ended_at"),
    }


@router.get("/build/status")
async def build_status(task_id: str):
    status = _load_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="status_not_found")
    return status


__all__ = [
    "router",
    "parse_director_intent",
]
