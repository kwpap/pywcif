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


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add ``--run-live`` to opt in to tests that call the real WCA API."""
    parser.addoption(
        "--run-live",
        action="store_true",
        default=False,
        help="run tests marked 'live', which download real WCIFs from the WCA website",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip 'live' tests unless ``--run-live`` is given."""
    if config.getoption("--run-live"):
        return
    skip_live = pytest.mark.skip(reason="needs network; pass --run-live to run")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
