"""Shared pytest fixtures for the drum-notation backend test suite."""

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_ML_RESPONSE_PATH = FIXTURES_DIR / "ml_analyze_response.sample.json"


@pytest.fixture(scope="session")
def sample_ml_response() -> Dict[str, Any]:
    """The real (enriched) ML /analyze response sample.

    NOTE: ``event_count`` is 2216 in production; this fixture is a compact,
    representative slice (includes a polyphonic stack and triplet events).
    """
    with open(SAMPLE_ML_RESPONSE_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture()
def sample_ml_events(sample_ml_response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The raw ``events`` array from the ML sample."""
    return list(sample_ml_response["events"])
