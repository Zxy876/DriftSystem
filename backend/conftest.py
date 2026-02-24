"""Pytest configuration for DriftSystem backend."""

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "v118_semantic: validates v1.18 semantic-layer governance contracts",
    )
