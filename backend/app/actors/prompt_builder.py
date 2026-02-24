"""Prompt builder for actors (Issue 4.2).

模块角色：根据阶段与记忆构造提示文本，默认在模型关闭时返回确定性提示。
不做什么：不调用外部模型 API，不写入记忆，仅读取；不改变世界状态。
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from app.actors.memory_store import ActorMemoryStore, STAGES


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def build_prompt(
    actor_id: str,
    stage: str,
    script_beat: Dict[str, Any],
    *,
    store: ActorMemoryStore,
    session_id: Optional[str] = None,
) -> str:
    """构造演员提示。

    - 仅允许 stage ∈ {IMPORT, SET_DRESS, REHEARSE, TAKE}
    - MODEL_CALLS_ENABLED 默认关闭；关闭时返回确定性提示字符串
    - 读取 memory_store，不写入
    """

    if stage not in STAGES:
        msg = f"invalid stage: {stage}"
        raise ValueError(msg)

    memory = store.load_memory(actor_id, stage, session_id=session_id)
    model_enabled = _env_flag("MODEL_CALLS_ENABLED", default=False)

    parts = [
        f"[actor:{actor_id}] stage={stage}",
        f"mode={'llm' if model_enabled else 'dry'}",
        f"memory={json.dumps(memory, ensure_ascii=False)}",
        f"beat={json.dumps(script_beat, ensure_ascii=False)}",
    ]
    return "\n".join(parts)


__all__ = ["build_prompt"]
