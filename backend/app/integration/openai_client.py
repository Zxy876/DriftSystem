"""OpenAI Client wrapper (Issue 6.1).

模块角色：封装 OpenAI 调用入口，支持 dry-run 日志；默认 MODEL_CALLS_ENABLED=false。
不做什么：不管理上游 Feature Flag 之外的权限；不缓存对话；不写入世界状态。
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class OpenAIClient:
    api_key: Optional[str]
    timeout: float = 30.0
    dry_run: bool = True

    def _enabled(self) -> bool:
        flag = os.getenv("MODEL_CALLS_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
        return flag and not self.dry_run

    def chat(self, prompt: str, *, model: str = "gpt-4o-mini", metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = {"model": model, "prompt": prompt, "metadata": metadata or {}}
        if not self._enabled():
            logger.info("openai_dry_run", extra={"payload": payload})
            return {"status": "dry-run", "model": model, "prompt": prompt}

        if not self.api_key:
            msg = "OpenAI API key missing"
            raise RuntimeError(msg)

        try:
            # 这里不直接调用 SDK，避免依赖；实际环境可替换为 openai.ChatCompletion.create
            logger.info("openai_call", extra={"payload": payload})
            # mock response
            return {"status": "ok", "model": model, "prompt": prompt, "choices": ["stub"]}
        except Exception as exc:  # pragma: no cover - 防御性日志
            logger.exception("openai_call_failed")
            raise RuntimeError("OpenAI call failed") from exc


__all__ = ["OpenAIClient"]
