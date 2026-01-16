"""Creation intent classification utilities for chat input.

This module provides a rule-first classifier that decides whether a chat
message represents a *creation* behaviour inside Drift System. The classifier
is intentionally conservative: it only returns a positive decision when the
player describes a construction/placement action that can plausibly produce a
world patch. Ambiguous chatter remains classified as non-creation so downstream
systems can request clarification instead of hallucinating patches.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = BACKEND_ROOT / "data" / "intent"
DEFAULT_KEYWORD_FILE = DATA_ROOT / "creation_keywords.json"


@dataclass
class CreationIntentDecision:
    """Classifier decision for a chat message."""

    is_creation: bool
    confidence: float
    reasons: List[str] = field(default_factory=list)
    slots: Dict[str, Iterable[str]] = field(default_factory=dict)

    def model_dump(self) -> Dict[str, object]:
        return {
            "is_creation": self.is_creation,
            "confidence": round(self.confidence, 3),
            "reasons": list(self.reasons),
            "slots": {key: list(value) for key, value in self.slots.items()},
        }


class CreationIntentClassifier:
    """Heuristic classifier for creation behaviours."""

    def __init__(
        self,
        *,
        keyword_path: Path = DEFAULT_KEYWORD_FILE,
        extra_action_keywords: Optional[Sequence[str]] = None,
        extra_material_keywords: Optional[Sequence[str]] = None,
        extra_non_creation_keywords: Optional[Sequence[str]] = None,
    ) -> None:
        raw = self._load_keyword_payload(keyword_path)
        action_words = self._normalise_keywords(raw.get("action_keywords", []))
        material_words = self._normalise_keywords(raw.get("material_keywords", []))
        non_creation_words = self._normalise_keywords(raw.get("non_creation_keywords", []))
        boost_words = self._normalise_keywords(raw.get("boost_phrases", []))

        if extra_action_keywords:
            action_words.update(self._normalise_keywords(extra_action_keywords))
        if extra_material_keywords:
            material_words.update(self._normalise_keywords(extra_material_keywords))
        if extra_non_creation_keywords:
            non_creation_words.update(self._normalise_keywords(extra_non_creation_keywords))

        self._action_keywords = action_words
        self._material_keywords = material_words
        self._non_creation_keywords = non_creation_words
        self._boost_keywords = boost_words

        self._action_pattern = self._compile_pattern(self._action_keywords)
        self._material_pattern = self._compile_pattern(self._material_keywords)
        self._non_creation_pattern = self._compile_pattern(self._non_creation_keywords)

    def classify(self, message: str) -> CreationIntentDecision:
        if not message or not message.strip():
            return CreationIntentDecision(
                is_creation=False,
                confidence=0.0,
                reasons=["empty_message"],
            )

        text = message.strip().lower()
        text_compact = re.sub(r"\s+", "", text)

        action_hits = self._find_keywords(self._action_pattern, text)
        material_hits = self._find_keywords(self._material_pattern, text)
        negative_hits = self._find_keywords(self._non_creation_pattern, text)
        boost_hits = [word for word in self._boost_keywords if word in text or word in text_compact]

        reasons: List[str] = []
        slots: Dict[str, Iterable[str]] = {}

        if action_hits:
            reasons.append(f"action:{'|'.join(action_hits)}")
            slots["actions"] = action_hits
        if material_hits:
            reasons.append(f"material:{'|'.join(material_hits)}")
            slots["materials"] = material_hits
        if boost_hits:
            reasons.append(f"boost:{'|'.join(boost_hits)}")

        # Negative evidence strongly reduces confidence
        negative_score = 0.0
        if negative_hits:
            reasons.append(f"non_creation:{'|'.join(negative_hits)}")
            negative_score = min(len(negative_hits) * 0.25, 0.6)

        action_score = min(len(action_hits) * 0.35, 0.7)
        material_score = min(len(material_hits) * 0.2, 0.4)
        boost_score = min(len(boost_hits) * 0.1, 0.2)

        confidence = max(action_score, 0.05) + material_score + boost_score - negative_score
        confidence = max(min(confidence, 1.0), 0.0)

        is_creation = confidence >= 0.45 and bool(action_hits)
        if negative_hits and len(action_hits) <= len(negative_hits):
            is_creation = False

        if not is_creation and confidence > 0.2:
            # downgrade when evidence is ambiguous
            reasons.append("ambiguous_context")

        return CreationIntentDecision(
            is_creation=is_creation,
            confidence=confidence,
            reasons=reasons,
            slots=slots,
        )

    @staticmethod
    def _load_keyword_payload(path: Path) -> Dict[str, List[str]]:
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _normalise_keywords(values: Iterable[str]) -> Set[str]:
        normalised: Set[str] = set()
        for value in values:
            if not value:
                continue
            token = str(value).strip().lower()
            if token:
                normalised.add(token)
        return normalised

    @staticmethod
    def _compile_pattern(keywords: Set[str]) -> Optional[re.Pattern[str]]:
        if not keywords:
            return None
        escaped = sorted({re.escape(word) for word in keywords if word})
        if not escaped:
            return None
        pattern = r"(" + "|".join(escaped) + r")"
        return re.compile(pattern, re.IGNORECASE)

    @staticmethod
    def _find_keywords(pattern: Optional[re.Pattern[str]], text: str) -> List[str]:
        if pattern is None:
            return []
        return sorted({match.group(0).lower() for match in pattern.finditer(text)})


_default_classifier: Optional[CreationIntentClassifier] = None


def default_creation_classifier() -> CreationIntentClassifier:
    global _default_classifier
    if _default_classifier is None:
        _default_classifier = CreationIntentClassifier()
    return _default_classifier