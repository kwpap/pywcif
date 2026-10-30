"""Round-trip and helper checks against real WCIF documents from the WCA website.

Two kinds of tests live here:

* **Recorded** tests run on every ``pytest`` invocation (and in CI). They use public WCIF
  snapshots stored in ``tests/fixtures/real/*.json``; add more with
  ``python scripts/snapshot_wcif.py <CompetitionId> ...``.
* **Live** tests (marker ``live``) download fresh WCIFs and only run with ``--run-live``.
  Override the competitions with ``PYWCIF_LIVE_COMPETITIONS="WC2025,Euro2024"`` and set
  ``PYWCIF_LIVE_SNAPSHOT_DIR`` to save every downloaded document for later inspection.
"""

from __future__ import annotations

import json
import os
import urllib.error
from pathlib import Path
from typing import Any

import pytest

from pywcif import fetch_wcif_dict
from tests.wcif_checks import assert_lossless_round_trip, exercise_helpers, summarize_diffs

REAL_DIR = Path(__file__).resolve().parent / "fixtures" / "real"
RECORDED = sorted(REAL_DIR.glob("*.json"))

# A spread of eras and sizes: very old data, a large modern championship, recent events.
DEFAULT_LIVE_COMPETITIONS = ("WC2007", "WC2019", "WC2023", "Euro2024", "WC2025")


def _live_competitions() -> list[str]:
    raw = os.environ.get("PYWCIF_LIVE_COMPETITIONS", "")
    chosen = [part.strip() for part in raw.split(",") if part.strip()]
    return chosen or list(DEFAULT_LIVE_COMPETITIONS)


def _load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data: dict[str, Any] = json.load(handle)
    return data


@pytest.mark.skipif(not RECORDED, reason="no snapshots in tests/fixtures/real yet")
@pytest.mark.parametrize("path", RECORDED, ids=[path.stem for path in RECORDED])
def test_recorded_wcif_round_trips_losslessly(path: Path) -> None:
    assert_lossless_round_trip(_load(path))


@pytest.mark.skipif(not RECORDED, reason="no snapshots in tests/fixtures/real yet")
@pytest.mark.parametrize("path", RECORDED, ids=[path.stem for path in RECORDED])
def test_recorded_wcif_helpers_and_audit_run(path: Path) -> None:
    exercise_helpers(assert_lossless_round_trip(_load(path)))


@pytest.mark.live
@pytest.mark.parametrize("competition_id", _live_competitions())
def test_live_wcif_round_trips_losslessly(competition_id: str) -> None:
    try:
        data = fetch_wcif_dict(competition_id, timeout=60.0)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            pytest.skip(f"{competition_id} not found on the WCA website")
        raise

    snapshot_dir = os.environ.get("PYWCIF_LIVE_SNAPSHOT_DIR")
    if snapshot_dir:
        target = Path(snapshot_dir) / f"{competition_id}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    exercise_helpers(assert_lossless_round_trip(data))


def test_checker_accepts_the_sample_fixture(sample_dict: dict[str, Any]) -> None:
    exercise_helpers(assert_lossless_round_trip(sample_dict))


def test_checker_reports_dropped_and_added_keys(sample_dict: dict[str, Any]) -> None:
    del sample_dict["persons"][0]["extensions"]  # pywcif will add it back as []
    with pytest.raises(AssertionError, match=r"\$\.persons\[0\]\.extensions: added by pywcif"):
        assert_lossless_round_trip(sample_dict)


def test_diff_summary_groups_repeated_paths() -> None:
    summary = summarize_diffs(
        [
            "$.a[0].b: added by pywcif (value None)",
            "$.a[1].b: added by pywcif (value None)",
            "$.c: 1 -> 2",
        ]
    )
    assert "2 x $.a[*].b: added by pywcif" in summary
    assert "1 x $.c: changed" in summary
