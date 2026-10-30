"""Tests for the WCA regulation and schedule auditor in :mod:`pywcif.audit`."""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from pywcif.audit import (
    CUTOFF_GE_TIMELIMIT,
    MISSING_ADVANCEMENT_CONDITION,
    REG_9P1_ADVANCEMENT,
    SCHEDULE_CONFLICT,
    UNMAPPED_ACTIVITY_ID,
    AuditIssue,
    audit_competition,
)
from pywcif.models import Competition

ATHENS_DAY = "2026-11-07"


def _at(hhmm: str) -> str:
    """Return a timestamp on the test day at the given local Athens time (UTC+2)."""
    return f"{ATHENS_DAY}T{hhmm}:00+02:00"


def _activity(
    activity_id: int,
    code: str,
    start: str,
    end: str,
    children: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": activity_id,
        "name": f"Activity {activity_id}",
        "activityCode": code,
        "startTime": start,
        "endTime": end,
        "childActivities": children or [],
        "extensions": [],
    }


def _round(round_id: str, **overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": round_id,
        "format": "a",
        "timeLimit": None,
        "cutoff": None,
        "advancementCondition": None,
        "results": [],
        "scrambleSetCount": 1,
        "extensions": [],
    }
    data.update(overrides)
    return data


def _base() -> dict[str, Any]:
    """Return a valid, issue-free competition document. Tests mutate their own copy."""
    return {
        "formatVersion": "1.0",
        "id": "TestOpen2026",
        "name": "Test Open 2026",
        "shortName": "Test Open",
        "persons": [],
        "events": [
            {
                "id": "333",
                "rounds": [
                    _round(
                        "333-r1",
                        timeLimit={"centiseconds": 60000, "cumulativeRoundIds": []},
                        cutoff={"numberOfAttempts": 2, "attemptResult": 6000},
                        advancementCondition={"type": "ranking", "level": 6},
                    ),
                    _round("333-r2"),
                ],
                "extensions": [],
            }
        ],
        "schedule": {
            "startDate": ATHENS_DAY,
            "numberOfDays": 1,
            "venues": [
                {
                    "id": 1,
                    "name": "Athens Venue",
                    "latitudeMicrodegrees": 37983000,
                    "longitudeMicrodegrees": 23727000,
                    "countryIso2": "GR",
                    "timezone": "Europe/Athens",
                    "rooms": [
                        {
                            "id": 10,
                            "name": "Main Hall",
                            "color": "#2e7d32",
                            "activities": [
                                _activity(
                                    100,
                                    "333-r1",
                                    _at("09:00"),
                                    _at("10:00"),
                                    children=[
                                        _activity(101, "333-r1-g1", _at("09:00"), _at("09:30"))
                                    ],
                                )
                            ],
                            "extensions": [],
                        }
                    ],
                    "extensions": [],
                }
            ],
        },
        "extensions": [],
    }


def _person(
    registrant_id: int,
    *,
    activity_ids: list[int] | None = None,
    status: str = "accepted",
    event_ids: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "registrantId": registrant_id,
        "name": f"Person {registrant_id}",
        "wcaUserId": 1000 + registrant_id,
        "wcaId": None,
        "countryIso2": "GR",
        "gender": "m",
        "roles": [],
        "registration": {
            "wcaRegistrationId": registrant_id,
            "eventIds": ["444"] if event_ids is None else event_ids,
            "status": status,
            "isCompeting": True,
        },
        "assignments": [
            {"activityId": activity_id, "assignmentCode": "competitor", "stationNumber": None}
            for activity_id in activity_ids or []
        ],
        "personalBests": [],
        "extensions": [],
    }


def _rounds(data: dict[str, Any]) -> list[dict[str, Any]]:
    rounds: list[dict[str, Any]] = data["events"][0]["rounds"]
    return rounds


def _room_activities(data: dict[str, Any]) -> list[dict[str, Any]]:
    activities: list[dict[str, Any]] = data["schedule"]["venues"][0]["rooms"][0]["activities"]
    return activities


def _run(data: dict[str, Any]) -> list[AuditIssue]:
    return audit_competition(Competition.model_validate(data))


def _codes(issues: list[AuditIssue]) -> list[str]:
    return [issue.code for issue in issues]


def _with_middle_round(data: dict[str, Any], condition: dict[str, Any] | None) -> None:
    """Insert a non-final round between the existing first and final rounds."""
    _rounds(data).insert(1, _round("333-mid", advancementCondition=condition))


def _with_schedule(data: dict[str, Any], *activities: dict[str, Any]) -> dict[str, Any]:
    _room_activities(data).extend(activities)
    return data


# Clean document and the AuditIssue type


def test_clean_competition_has_no_issues() -> None:
    assert _run(_base()) == []


def test_audit_issue_defaults_and_is_frozen() -> None:
    issue = AuditIssue(code="X", severity="error", message="msg")
    assert issue.context == {}
    with pytest.raises(dataclasses.FrozenInstanceError):
        issue.code = "Y"  # type: ignore[misc]


# CUTOFF_GE_TIMELIMIT


@pytest.mark.parametrize(
    ("attempt_result", "expected"),
    [
        (5999, []),
        (6000, [CUTOFF_GE_TIMELIMIT]),
        (6001, [CUTOFF_GE_TIMELIMIT]),
    ],
)
def test_cutoff_compared_to_time_limit(attempt_result: int, expected: list[str]) -> None:
    data = _base()
    _rounds(data)[0]["timeLimit"]["centiseconds"] = 6000
    _rounds(data)[0]["cutoff"]["attemptResult"] = attempt_result
    assert _codes(_run(data)) == expected


def test_cutoff_issue_has_error_severity_and_context() -> None:
    data = _base()
    _rounds(data)[0]["timeLimit"]["centiseconds"] = 6000
    _rounds(data)[0]["cutoff"]["attemptResult"] = 6000
    [issue] = _run(data)
    assert issue.code == CUTOFF_GE_TIMELIMIT
    assert issue.severity == "error"
    assert issue.context["event_id"] == "333"
    assert issue.context["round_id"] == "333-r1"
    assert issue.context["cutoff_centiseconds"] == 6000
    assert issue.context["time_limit_centiseconds"] == 6000


def test_cumulative_time_limit_is_skipped() -> None:
    data = _base()
    round_two = _rounds(data)[1]
    round_two["timeLimit"] = {"centiseconds": 60000, "cumulativeRoundIds": ["333-r1"]}
    round_two["cutoff"] = {"numberOfAttempts": 2, "attemptResult": 61000}
    assert _run(data) == []


def test_cutoff_without_time_limit_or_time_limit_without_cutoff_is_skipped() -> None:
    data = _base()
    _rounds(data)[0]["timeLimit"] = None
    _rounds(data)[0]["cutoff"]["attemptResult"] = 999999
    assert _run(data) == []

    data = _base()
    _rounds(data)[0]["cutoff"] = None
    assert _run(data) == []


# MISSING_ADVANCEMENT_CONDITION


def test_non_final_round_without_condition_is_flagged() -> None:
    data = _base()
    _rounds(data)[0]["advancementCondition"] = None
    [issue] = _run(data)
    assert issue.code == MISSING_ADVANCEMENT_CONDITION
    assert issue.severity == "error"
    assert issue.context["round_id"] == "333-r1"
    assert issue.context["is_final"] is False


def test_final_round_with_condition_is_flagged() -> None:
    data = _base()
    _rounds(data)[1]["advancementCondition"] = {"type": "ranking", "level": 2}
    [issue] = _run(data)
    assert issue.code == MISSING_ADVANCEMENT_CONDITION
    assert issue.severity == "error"
    assert issue.context["round_id"] == "333-r2"
    assert issue.context["is_final"] is True


def test_single_round_event_needs_no_condition() -> None:
    data = _base()
    data["events"] = [{"id": "444", "rounds": [_round("444-r1")], "extensions": []}]
    assert _run(data) == []

    data["events"][0]["rounds"][0]["advancementCondition"] = {"type": "ranking", "level": 1}
    assert _codes(_run(data)) == [MISSING_ADVANCEMENT_CONDITION]


def test_event_without_rounds_is_ignored() -> None:
    data = _base()
    data["events"] = [{"id": "444"}]
    assert _run(data) == []


# REG_9P1_ADVANCEMENT: percent


@pytest.mark.parametrize(("level", "expected"), [(75, []), (76, [REG_9P1_ADVANCEMENT])])
def test_percent_above_75_is_flagged(level: int, expected: list[str]) -> None:
    data = _base()
    _rounds(data)[0]["advancementCondition"] = {"type": "percent", "level": level}
    assert _codes(_run(data)) == expected


def test_percent_issue_has_error_severity_and_context() -> None:
    data = _base()
    _rounds(data)[0]["advancementCondition"] = {"type": "percent", "level": 80}
    [issue] = _run(data)
    assert issue.severity == "error"
    assert issue.context["round_id"] == "333-r1"
    assert issue.context["type"] == "percent"
    assert issue.context["level"] == 80


def test_percent_rule_applies_to_middle_rounds() -> None:
    data = _base()
    _with_middle_round(data, {"type": "percent", "level": 80})
    [issue] = _run(data)
    assert issue.code == REG_9P1_ADVANCEMENT
    assert issue.context["round_id"] == "333-mid"


# REG_9P1_ADVANCEMENT: ranking on round 1


def _competitors(count: int, *, status: str = "accepted") -> list[dict[str, Any]]:
    return [
        _person(registrant_id, status=status, event_ids=["333"])
        for registrant_id in range(1, count + 1)
    ]


@pytest.mark.parametrize(
    ("competitors", "level", "flagged"),
    [
        (8, 6, False),
        (8, 7, True),
        (10, 7, False),
        (10, 8, True),
        (1, 0, False),
        (1, 1, True),
    ],
)
def test_ranking_on_round_one_compared_to_75_percent_of_accepted(
    competitors: int, level: int, flagged: bool
) -> None:
    data = _base()
    data["persons"] = _competitors(competitors)
    _rounds(data)[0]["advancementCondition"] = {"type": "ranking", "level": level}
    assert _codes(_run(data)) == ([REG_9P1_ADVANCEMENT] if flagged else [])


def test_ranking_issue_context_reports_counts() -> None:
    data = _base()
    data["persons"] = _competitors(8)
    _rounds(data)[0]["advancementCondition"] = {"type": "ranking", "level": 7}
    [issue] = _run(data)
    assert issue.code == REG_9P1_ADVANCEMENT
    assert issue.severity == "error"
    assert issue.context["event_id"] == "333"
    assert issue.context["round_id"] == "333-r1"
    assert issue.context["accepted_competitors"] == 8
    assert issue.context["max_level"] == 6


def test_ranking_counts_only_accepted_competitors_of_the_event() -> None:
    data = _base()
    data["persons"] = (
        _competitors(8)
        + [_person(100 + i, status="pending") for i in range(5)]
        + [_person(200 + i, event_ids=["444"]) for i in range(3)]
    )
    _rounds(data)[0]["advancementCondition"] = {"type": "ranking", "level": 6}
    assert _run(data) == []

    _rounds(data)[0]["advancementCondition"] = {"type": "ranking", "level": 7}
    [issue] = _run(data)
    assert issue.context["accepted_competitors"] == 8


def test_ranking_with_zero_accepted_competitors_is_skipped() -> None:
    data = _base()
    _rounds(data)[0]["advancementCondition"] = {"type": "ranking", "level": 100}
    assert _run(data) == []


def test_ranking_rule_only_checks_round_one() -> None:
    data = _base()
    data["persons"] = _competitors(8)
    _with_middle_round(data, {"type": "ranking", "level": 100})
    assert _run(data) == []


# UNMAPPED_ACTIVITY_ID


def test_unmapped_activity_is_flagged() -> None:
    data = _base()
    data["persons"] = [_person(1, activity_ids=[999])]
    [issue] = _run(data)
    assert issue.code == UNMAPPED_ACTIVITY_ID
    assert issue.severity == "error"
    assert issue.context["activity_id"] == 999
    assert issue.context["registrant_id"] == 1
    assert issue.context["person_name"] == "Person 1"


def test_child_activity_counts_as_mapped() -> None:
    data = _base()
    data["persons"] = [_person(1, activity_ids=[100, 101])]
    assert _run(data) == []


# SCHEDULE_CONFLICT


def _unrelated_activities() -> list[dict[str, Any]]:
    """Top-level, non-competition activities that overlap or touch each other."""
    return [
        _activity(200, "other-lunch", _at("12:00"), _at("13:00")),
        _activity(201, "other-tutorial", _at("12:30"), _at("13:30")),
        _activity(202, "other-break", _at("13:00"), _at("14:00")),
        _activity(203, "other-third", _at("12:45"), _at("13:15")),
    ]


def test_overlapping_unrelated_activities_are_flagged_once() -> None:
    data = _with_schedule(_base(), *_unrelated_activities())
    data["persons"] = [_person(1, activity_ids=[200, 201])]
    [issue] = _run(data)
    assert issue.code == SCHEDULE_CONFLICT
    assert issue.severity == "warning"
    assert issue.context["registrant_id"] == 1
    assert issue.context["activity_ids"] == [200, 201]
    assert issue.context["activity_codes"] == ["other-lunch", "other-tutorial"]


def test_adjacent_activities_are_not_a_conflict() -> None:
    data = _with_schedule(_base(), *_unrelated_activities())
    data["persons"] = [_person(1, activity_ids=[200, 202])]
    assert _run(data) == []


def test_parent_and_child_overlap_is_ignored() -> None:
    data = _base()
    data["persons"] = [_person(1, activity_ids=[100, 101])]
    assert _run(data) == []


def test_tree_ancestor_with_unofficial_codes_is_ignored() -> None:
    outer = _activity(
        210,
        "other-block",
        _at("12:00"),
        _at("14:00"),
        children=[_activity(211, "other-inner", _at("12:30"), _at("13:00"))],
    )
    data = _with_schedule(_base(), outer)
    data["persons"] = [_person(1, activity_ids=[210, 211])]
    assert _run(data) == []


def test_code_parent_without_tree_link_is_ignored() -> None:
    data = _with_schedule(
        _base(),
        _activity(220, "333", _at("09:00"), _at("10:00")),
        _activity(221, "333-r1-g2", _at("09:00"), _at("09:30")),
    )
    data["persons"] = [_person(1, activity_ids=[220, 221])]
    assert _run(data) == []


def test_unparsable_activity_code_is_treated_as_unrelated() -> None:
    data = _with_schedule(
        _base(),
        *_unrelated_activities(),
        _activity(230, "333-zz", _at("12:30"), _at("13:30")),
    )
    data["persons"] = [_person(1, activity_ids=[200, 230])]
    assert _codes(_run(data)) == [SCHEDULE_CONFLICT]


def test_same_activity_twice_is_not_a_conflict() -> None:
    data = _with_schedule(_base(), *_unrelated_activities())
    data["persons"] = [_person(1, activity_ids=[200, 200])]
    assert _run(data) == []


def test_each_overlapping_pair_is_reported_once() -> None:
    data = _with_schedule(_base(), *_unrelated_activities())
    data["persons"] = [_person(1, activity_ids=[200, 201, 203])]
    issues = _run(data)
    assert _codes(issues) == [SCHEDULE_CONFLICT] * 3
    pairs = {tuple(issue.context["activity_ids"]) for issue in issues}
    assert pairs == {(200, 201), (200, 203), (201, 203)}


def test_duplicate_assignment_does_not_duplicate_the_conflict() -> None:
    data = _with_schedule(_base(), *_unrelated_activities())
    data["persons"] = [_person(1, activity_ids=[200, 200, 201])]
    assert _codes(_run(data)) == [SCHEDULE_CONFLICT]


def test_conflicts_are_per_person() -> None:
    data = _with_schedule(_base(), *_unrelated_activities())
    data["persons"] = [_person(1, activity_ids=[200]), _person(2, activity_ids=[201])]
    assert _run(data) == []


def test_unmapped_assignment_is_not_used_for_conflicts() -> None:
    data = _with_schedule(_base(), *_unrelated_activities())
    data["persons"] = [_person(1, activity_ids=[200, 999])]
    assert _codes(_run(data)) == [UNMAPPED_ACTIVITY_ID]


def test_overlap_compares_instants_across_utc_offsets() -> None:
    # 200 is 10:00-11:00 UTC. 240 starts at 12:30 UTC, so it is later even though
    # its wall-clock text sorts before 200's end time.
    utc_later = _activity(
        240, "other-utc", "2026-11-07T12:30:00+00:00", "2026-11-07T13:30:00+00:00"
    )
    data = _with_schedule(_base(), *_unrelated_activities(), utc_later)
    data["persons"] = [_person(1, activity_ids=[200, 240])]
    assert _run(data) == []

    utc_overlapping = _activity(241, "other-utc2", "2026-11-07T10:30:00Z", "2026-11-07T11:30:00Z")
    data = _with_schedule(_base(), *_unrelated_activities(), utc_overlapping)
    data["persons"] = [_person(1, activity_ids=[200, 241])]
    assert _codes(_run(data)) == [SCHEDULE_CONFLICT]


def test_unparseable_times_are_skipped_without_raising() -> None:
    broken = _activity(250, "other-broken", "not-a-time", _at("13:00"))
    data = _with_schedule(_base(), *_unrelated_activities(), broken)
    data["persons"] = [_person(1, activity_ids=[200, 250])]
    assert _run(data) == []


# Odd or empty data must not raise


def test_empty_competition_has_no_issues() -> None:
    data = _base()
    data["events"] = []
    data["persons"] = []
    data["schedule"]["venues"] = []
    assert _run(data) == []


def test_incomplete_data_does_not_raise() -> None:
    data = _base()
    data["events"] = [{"id": "444"}]
    data["schedule"]["venues"][0]["rooms"] = [
        {"id": 11, "name": "Empty", "color": "#000000", "activities": []}
    ]
    data["persons"] = [_person(1, activity_ids=[999])]
    assert _codes(_run(data)) == [UNMAPPED_ACTIVITY_ID]
