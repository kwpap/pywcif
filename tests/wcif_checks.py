"""Checks shared by the recorded and live real-world WCIF tests."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from pywcif import ActivityCode, Competition, audit_competition

_MISSING = object()
MAX_REPORTED_DIFFS = 25


def iter_json_diffs(expected: Any, actual: Any, path: str = "$") -> Iterator[str]:
    """Yield one human-readable line per difference between two decoded JSON values."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in expected.keys() | actual.keys():
            sub = f"{path}.{key}"
            left = expected.get(key, _MISSING)
            right = actual.get(key, _MISSING)
            if left is _MISSING:
                yield f"{sub}: added by pywcif (value {right!r:.80})"
            elif right is _MISSING:
                yield f"{sub}: dropped by pywcif (input had {left!r:.80})"
            else:
                yield from iter_json_diffs(left, right, sub)
    elif isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            yield f"{path}: list length {len(expected)} -> {len(actual)}"
        for index, (left, right) in enumerate(zip(expected, actual, strict=False)):
            yield from iter_json_diffs(left, right, f"{path}[{index}]")
    elif type(expected) is not type(actual) or expected != actual:
        yield f"{path}: {expected!r:.80} -> {actual!r:.80}"


def assert_lossless_round_trip(data: dict[str, Any]) -> Competition:
    """Validate ``data`` and assert that dumping it back gives exactly the same dict."""
    comp = Competition.model_validate(data)
    diffs = list(iter_json_diffs(data, comp.to_wcif_dict()))
    if diffs:
        shown = "\n".join(diffs[:MAX_REPORTED_DIFFS])
        more = len(diffs) - MAX_REPORTED_DIFFS
        suffix = f"\n... and {more} more" if more > 0 else ""
        raise AssertionError(
            f"{comp.id}: round-trip changed {len(diffs)} value(s):\n{shown}{suffix}"
        )
    return comp


def exercise_helpers(comp: Competition) -> None:
    """Run the query helpers and the auditor over a real document; they must not raise."""
    activities = list(comp.iter_activities())
    for _venue, _room, activity in activities:
        assert activity.start_dt <= activity.end_dt, activity.id
        ActivityCode.parse(activity.activity_code)
    for person in comp.persons:
        if person.registrant_id is not None:
            entries = comp.get_person_schedule(person.registrant_id)
            starts = [entry.local_start for entry in entries]
            assert starts == sorted(starts)
    comp.get_accepted_competitors()
    comp.get_first_timers()
    comp.get_staff()
    for event in comp.events:
        assert comp.get_event(str(event.id)) is event
        for round_ in event.rounds:
            assert comp.get_round(round_.id) is round_
    issues = audit_competition(comp)
    assert all(issue.severity in ("error", "warning") for issue in issues)
