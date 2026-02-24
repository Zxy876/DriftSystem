"""Contract tests for v1.18 semantic comment requirements."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.v118_semantic
def test_v118_comment_validator_passes() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    script = backend_root / "tools" / "validate_v118_comments.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        check=False,
    )
    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    output = "\n".join(filter(None, [stdout, stderr]))
    assert result.returncode == 0, f"validator failed:\n{output}"
