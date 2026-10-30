"""Validation and auditing entry points for WCIF payloads.

:func:`audit_competition` runs a fixed set of WCA regulation and schedule checks over a loaded
:class:`~pywcif.models.Competition` and returns the findings as :class:`AuditIssue` objects.
The checks skip missing optional data rather than raising, so incomplete documents can be audited.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from pywcif.activity_code import ActivityCode
from pywcif.models import Activity, Competition

__all__ = [
    "CUTOFF_GE_TIMELIMIT",
    "MISSING_ADVANCEMENT_CONDITION",
    "REG_9P1_ADVANCEMENT",
    "SCHEDULE_CONFLICT",
    "UNMAPPED_ACTIVITY_ID",
    "AuditIssue",
    "audit_competition",
]

CUTOFF_GE_TIMELIMIT = "CUTOFF_GE_TIMELIMIT"
MISSING_ADVANCEMENT_CONDITION = "MISSING_ADVANCEMENT_CONDITION"
REG_9P1_ADVANCEMENT = "REG_9P1_ADVANCEMENT"
UNMAPPED_ACTIVITY_ID = "UNMAPPED_ACTIVITY_ID"
SCHEDULE_CONFLICT = "SCHEDULE_CONFLICT"

# Regulation 9p1: at least 25% of competitors must be eliminated between rounds.
_MAX_PERCENT_LEVEL = 75
_RANKING_KEEP_FRACTION = 0.75

_PERCENT = "percent"
_RANKING = "ranking"

_Span = tuple[datetime, datetime]


@dataclass(frozen=True)
class AuditIssue:
    """A single finding from :func:`audit_competition`.

    Attributes:
        code: Stable rule identifier, one of the ``*`` code constants in this module.
        severity: ``"error"`` for a rule violation, ``"warning"`` for a likely problem.
        message: Human-readable description.
        context: Identifiers and values behind the finding, such as ``event_id``,
            ``round_id``, ``registrant_id`` or ``activity_ids``.
    """

    code: str
    severity: Literal["error", "warning"]
    message: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class _ScheduleIndex:
    """Lookup tables built once per audit.

    ``activities`` maps an activity id to its first occurrence in the schedule (children included).
    ``ancestors`` maps an activity id to the ids of every activity above it in the schedule tree.
    """

    activities: dict[int, Activity] = field(default_factory=dict)
    ancestors: dict[int, set[int]] = field(default_factory=dict)


def audit_competition(comp: Competition) -> list[AuditIssue]:
    """Run every audit check and return the combined findings.

    The checks are: cutoff against time limit, advancement condition presence, Regulation 9p1
    advancement levels, unmapped assignment activity ids, and overlapping personal assignments.

    Args:
        comp: The competition to audit.

    Returns:
        The issues found, in check order. An empty list means no issues were found.
    """
    index = _build_index(comp)
    return [
        *_check_cutoff_against_time_limit(comp),
        *_check_advancement_conditions(comp),
        *_check_regulation_9p1(comp),
        *_check_unmapped_activities(comp, index),
        *_check_schedule_conflicts(comp, index),
    ]


def _check_cutoff_against_time_limit(comp: Competition) -> list[AuditIssue]:
    """Flag rounds whose cutoff is not strictly below their (non-cumulative) time limit."""
    issues: list[AuditIssue] = []
    for event in comp.events:
        event_id = str(event.id)
        for round_ in event.rounds:
            cutoff = round_.cutoff
            time_limit = round_.time_limit
            if cutoff is None or time_limit is None or time_limit.cumulative_round_ids:
                continue
            if cutoff.attempt_result >= time_limit.centiseconds:
                issues.append(
                    AuditIssue(
                        code=CUTOFF_GE_TIMELIMIT,
                        severity="error",
                        message=(
                            f"Round {round_.id} of event {event_id} has a cutoff of "
                            f"{cutoff.attempt_result} cs, which is not below its time limit of "
                            f"{time_limit.centiseconds} cs"
                        ),
                        context={
                            "event_id": event_id,
                            "round_id": round_.id,
                            "cutoff_centiseconds": cutoff.attempt_result,
                            "time_limit_centiseconds": time_limit.centiseconds,
                        },
                    )
                )
    return issues


def _check_advancement_conditions(comp: Competition) -> list[AuditIssue]:
    """Require an advancement condition on every non-final round and none on the final round."""
    issues: list[AuditIssue] = []
    for event in comp.events:
        event_id = str(event.id)
        last_index = len(event.rounds) - 1
        for index, round_ in enumerate(event.rounds):
            is_final = index == last_index
            has_condition = round_.advancement_condition is not None
            if is_final and has_condition:
                message = (
                    f"Final round {round_.id} of event {event_id} must not have an "
                    "advancement condition"
                )
            elif not is_final and not has_condition:
                message = (
                    f"Round {round_.id} of event {event_id} is not the final round but has no "
                    "advancement condition"
                )
            else:
                continue
            issues.append(
                AuditIssue(
                    code=MISSING_ADVANCEMENT_CONDITION,
                    severity="error",
                    message=message,
                    context={
                        "event_id": event_id,
                        "round_id": round_.id,
                        "round_number": index + 1,
                        "is_final": is_final,
                    },
                )
            )
    return issues


def _check_regulation_9p1(comp: Competition) -> list[AuditIssue]:
    """Enforce Regulation 9p1: at least 25% of competitors must be eliminated between rounds.

    A ``percent`` condition may not exceed 75 on any round. A ``ranking`` condition on the first
    round may not exceed 75% of the accepted competitors for the event (rounded down). Rules are
    skipped when there are no accepted competitors.
    """
    issues: list[AuditIssue] = []
    for event in comp.events:
        event_id = str(event.id)
        for index, round_ in enumerate(event.rounds):
            condition = round_.advancement_condition
            if condition is None:
                continue
            if condition.type == _PERCENT and condition.level > _MAX_PERCENT_LEVEL:
                issues.append(
                    AuditIssue(
                        code=REG_9P1_ADVANCEMENT,
                        severity="error",
                        message=(
                            f"Round {round_.id} of event {event_id} advances "
                            f"{condition.level}% of competitors; Regulation 9p1 allows at most "
                            f"{_MAX_PERCENT_LEVEL}%"
                        ),
                        context={
                            "event_id": event_id,
                            "round_id": round_.id,
                            "type": _PERCENT,
                            "level": condition.level,
                            "max_level": _MAX_PERCENT_LEVEL,
                        },
                    )
                )
            elif condition.type == _RANKING and index == 0:
                accepted_count = len(comp.get_accepted_competitors(event.id))
                max_level = int(accepted_count * _RANKING_KEEP_FRACTION)
                if accepted_count > 0 and condition.level > max_level:
                    issues.append(
                        AuditIssue(
                            code=REG_9P1_ADVANCEMENT,
                            severity="error",
                            message=(
                                f"Round {round_.id} of event {event_id} advances "
                                f"{condition.level} competitors; Regulation 9p1 allows at most "
                                f"{max_level} of {accepted_count} accepted competitors"
                            ),
                            context={
                                "event_id": event_id,
                                "round_id": round_.id,
                                "type": _RANKING,
                                "level": condition.level,
                                "accepted_competitors": accepted_count,
                                "max_level": max_level,
                            },
                        )
                    )
    return issues


def _check_unmapped_activities(comp: Competition, index: _ScheduleIndex) -> list[AuditIssue]:
    """Flag assignments whose activity id does not exist anywhere in the schedule."""
    issues: list[AuditIssue] = []
    for person in comp.persons:
        for assignment in person.assignments:
            if assignment.activity_id in index.activities:
                continue
            issues.append(
                AuditIssue(
                    code=UNMAPPED_ACTIVITY_ID,
                    severity="error",
                    message=(
                        f"{person.name} is assigned to activity {assignment.activity_id}, "
                        "which is not in the schedule"
                    ),
                    context={
                        "registrant_id": person.registrant_id,
                        "person_name": person.name,
                        "activity_id": assignment.activity_id,
                        "assignment_code": str(assignment.assignment_code),
                    },
                )
            )
    return issues


def _check_schedule_conflicts(comp: Competition, index: _ScheduleIndex) -> list[AuditIssue]:
    """Warn about each pair of a person's activities whose time intervals overlap.

    Activities related by the schedule tree or by activity code (see
    :meth:`ActivityCode.is_parent_of`) are not conflicts. Each unordered pair of activity ids is
    reported once per person. Assignments to unmapped activities are skipped.
    """
    issues: list[AuditIssue] = []
    for person in comp.persons:
        placed = _placed_activities([a.activity_id for a in person.assignments], index)
        reported: set[tuple[int, int]] = set()
        for position, (first, first_span) in enumerate(placed):
            for second, second_span in placed[position + 1 :]:
                if first.id == second.id:
                    continue
                pair = (min(first.id, second.id), max(first.id, second.id))
                if pair in reported:
                    continue
                start = max(first_span[0], second_span[0])
                end = min(first_span[1], second_span[1])
                if start >= end or _are_related(first, second, index):
                    continue
                reported.add(pair)
                issues.append(
                    AuditIssue(
                        code=SCHEDULE_CONFLICT,
                        severity="warning",
                        message=(
                            f"{person.name} has overlapping assignments: "
                            f"{first.activity_code} ({first.name}) and "
                            f"{second.activity_code} ({second.name}) overlap from "
                            f"{start.isoformat()} to {end.isoformat()}"
                        ),
                        context={
                            "registrant_id": person.registrant_id,
                            "person_name": person.name,
                            "activity_ids": [first.id, second.id],
                            "activity_codes": [first.activity_code, second.activity_code],
                            "overlap_start": start.isoformat(),
                            "overlap_end": end.isoformat(),
                        },
                    )
                )
    return issues


def _build_index(comp: Competition) -> _ScheduleIndex:
    """Index every activity in the schedule, including nested child activities."""
    index = _ScheduleIndex()
    for venue in comp.schedule.venues:
        for room in venue.rooms:
            _index_activities(room.activities, (), index)
    return index


def _index_activities(
    activities: list[Activity], ancestor_ids: tuple[int, ...], index: _ScheduleIndex
) -> None:
    """Record each activity and its ancestor ids, then recurse into its children."""
    for activity in activities:
        index.activities.setdefault(activity.id, activity)
        index.ancestors.setdefault(activity.id, set()).update(ancestor_ids)
        _index_activities(activity.child_activities, (*ancestor_ids, activity.id), index)


def _placed_activities(
    activity_ids: list[int], index: _ScheduleIndex
) -> list[tuple[Activity, _Span]]:
    """Resolve activity ids to ``(activity, (start, end))``, dropping unmapped or untimed ones."""
    placed: list[tuple[Activity, _Span]] = []
    for activity_id in activity_ids:
        activity = index.activities.get(activity_id)
        if activity is None:
            continue
        span = _span(activity)
        if span is not None:
            placed.append((activity, span))
    return placed


def _span(activity: Activity) -> _Span | None:
    """Return the activity's UTC interval, or None if its times cannot be parsed."""
    try:
        return activity.start_dt, activity.end_dt
    except (ValueError, OverflowError):
        return None


def _are_related(first: Activity, second: Activity, index: _ScheduleIndex) -> bool:
    """Return whether one activity is an ancestor of the other, or a parent by activity code."""
    if first.id in index.ancestors.get(second.id, set()):
        return True
    if second.id in index.ancestors.get(first.id, set()):
        return True
    first_code = _parse_code(first)
    second_code = _parse_code(second)
    if first_code is None or second_code is None:
        return False
    return first_code.is_parent_of(second_code) or second_code.is_parent_of(first_code)


def _parse_code(activity: Activity) -> ActivityCode | None:
    """Parse an activity's code, returning None for codes that do not parse."""
    try:
        return ActivityCode.parse(activity.activity_code)
    except ValueError:
        return None
