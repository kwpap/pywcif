"""Shared pytest configuration and fixtures for pywcif tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pywcif.models import Competition

SAMPLE_PATH = Path(__file__).resolve().parent / "fixtures" / "sample_competition.json"


@pytest.fixture
def sample_path() -> Path:
    """Path to the sample WCIF fixture."""
    return SAMPLE_PATH


@pytest.fixture
def sample_dict() -> dict[str, Any]:
    """A freshly decoded copy of the sample WCIF document, safe to mutate."""
    with SAMPLE_PATH.open(encoding="utf-8") as handle:
        data: dict[str, Any] = json.load(handle)
    return data


@pytest.fixture
def sample_competition(sample_dict: dict[str, Any]) -> Competition:
    """The sample fixture validated into a Competition."""
    return Competition.model_validate(sample_dict)
