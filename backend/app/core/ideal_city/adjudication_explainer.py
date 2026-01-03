import json
import logging
from typing import Dict, Iterable, Optional

from .adjudication_contract import VerdictEnum
from ..ai.deepseek_agent import AI_DISABLED, call_deepseek

_log = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are the archivist of the Ideal City project. A deterministic verdict has already "
    "been issued; you only provide concise explanations or next-step framing. "
    "Return JSON with {\"explanation\": \"...\"}. Avoid contradicting the verdict."
)


class AdjudicationExplainer:
    """Optional AI enrichment that explains verdicts without affecting verdict outcome."""

    def __init__(self, enable_ai: Optional[bool] = None) -> None:
        self._enable_ai = (not AI_DISABLED) if enable_ai is None else enable_ai
        self._fallback_templates: Dict[VerdictEnum, str] = {
            VerdictEnum.ACCEPT: (
                "档案员说明：提案包含必要结构，可在工坊排期时继续补充建议条目。"
            ),
            VerdictEnum.REVIEW_REQUIRED: (
                "档案员说明：提案被标记为草稿，等待档案馆人工复核后再推进。"
            ),
            VerdictEnum.REJECT: (
                "档案员说明：提案缺少必要结构，需先补齐指导项后再提交审批。"
            ),
        }

    def build_explanation(self, verdict: VerdictEnum, guidance_lines: Iterable[str]) -> str:
        guidance_text = self._condense_guidance(guidance_lines)
        if not self._enable_ai:
            return self._fallback_templates.get(verdict, guidance_text)

        try:
            payload = {
                "task": "ideal_city_verdict_explainer",
                "verdict": verdict.value,
                "guidance": guidance_text,
            }
            response = call_deepseek(
                payload,
                [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                temperature=0.25,
            )
            parsed = response.get("parsed") if isinstance(response, dict) else None
            if isinstance(parsed, dict):
                explanation = parsed.get("explanation")
                if isinstance(explanation, str) and explanation.strip():
                    return explanation.strip()
        except Exception as exc:  # noqa: BLE001 - guardrail around AI optional path
            _log.warning("Adjudication explanation fallback after AI failure: %s", exc)

        return self._fallback_templates.get(verdict, guidance_text)

    @staticmethod
    def _condense_guidance(guidance_lines: Iterable[str]) -> str:
        lines = [line.strip() for line in guidance_lines if isinstance(line, str) and line.strip()]
        if not lines:
            return "No follow-up guidance generated."
        return "\n".join(lines)
