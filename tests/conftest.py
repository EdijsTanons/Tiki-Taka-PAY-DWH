"""Shared pytest fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def sample_response() -> dict:  # type: ignore[type-arg]
    return json.loads((FIXTURES_DIR / "sample_response.json").read_text(encoding="utf-8"))


@pytest.fixture()
def sample_docs(sample_response: dict) -> list[dict]:  # type: ignore[type-arg]
    return sample_response["results"]
