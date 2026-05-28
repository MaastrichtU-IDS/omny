"""Shared fixtures for the bench harness (not the unit-test suite)."""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PIZZA_OMN = REPO_ROOT / "tests" / "data" / "pizza.omn"
BIOMED_OMN = REPO_ROOT / "examples" / "data" / "biomed.omn"


@pytest.fixture
def pizza_text() -> str:
    return PIZZA_OMN.read_text()


@pytest.fixture
def biomed_text() -> str:
    return BIOMED_OMN.read_text()
