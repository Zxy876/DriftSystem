from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent
PARENT_ROOT = BACKEND_ROOT.parent
for candidate in (str(BACKEND_ROOT), str(PARENT_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.core.intent_creation import CreationIntentClassifier


def test_creation_classifier_positive_detection() -> None:
    classifier = CreationIntentClassifier()
    decision = classifier.classify("我想用紫水晶搭建一盏幽冥莲花灯")
    assert decision.is_creation is True
    assert decision.confidence >= 0.45
    assert "actions" in decision.slots
    assert "materials" in decision.slots


def test_creation_classifier_negative_detection() -> None:
    classifier = CreationIntentClassifier()
    decision = classifier.classify("今天的天气真不错，随便聊聊")
    assert decision.is_creation is False
    assert decision.confidence <= 0.4