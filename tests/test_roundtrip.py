"""Round-trip serialization and relational helper tests against the sample fixture."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from pywcif.models import Assignment, Competition
from pywcif.results import MultiBlindResult, format_result

RECONSTRUCTION = "R U2 R' F2 D' L2 B U' R2 F' U2 L D2 R' U2 F2 R2 D' B2 U2 L2"


# ---------------------------------------------------------------------------
# Helpers for navigating the raw WCIF dict
# ---------------------------------------------------------------------------


def _person_dict(doc: dict[str, Any], name: str) -> dict[str, Any]:
    matches: list[dict[str, Any]] = [p for p in doc["persons"] if p["name"] == name]
    assert len(matches) == 1, name
    return matches[0]


def _event_dict(doc: dict[str, Any], event_id: str) -> dict[str, Any]:
    matches: list[dict[str, Any]] = [e for e in doc["events"] if e["id"] == event_id]
    assert len(matches) == 1, event_id
    return matches[0]


def _iter_activity_dicts(nodes: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    for node in nodes:
        yield node
        yield from _iter_activity_dicts(node["childActivities"])


def _all_activity_dicts(doc: dict[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for venue in doc["schedule"]["venues"]:
        for room in venue["rooms"]:
            found.extend(_iter_activity_dicts(room["activities"]))
    return found


def _activity_dict(doc: dict[str, Any], activity_id: int) -> dict[str, Any]:
    matches = [a for a in _all_activity_dicts(doc) if a["id"] == activity_id]
    assert len(matches) == 1, activity_id
    return matches[0]


def _all_attempts(doc: dict[str, Any]) -> list[dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    for event in doc["events"]:
        for round_ in event["rounds"]:
            for result in round_["results"]:
                attempts.extend(result["attempts"])
    return attempts


# ---------------------------------------------------------------------------
# Exact and stable round-trips
# ---------------------------------------------------------------------------


def test_to_wcif_dict_equals_input_exactly(sample_dict: dict[str, Any]) -> None:
    comp = Competition.model_validate(sample_dict)
    assert comp.to_wcif_dict() == sample_dict


def test_compact_json_equals_input(sample_dict: dict[str, Any]) -> None:
    comp = Competition.model_validate(sample_dict)
    assert json.loads(comp.to_wcif_json()) == sample_dict


def test_indented_json_equals_input(sample_dict: dict[str, Any]) -> None:
    comp = Competition.model_validate(sample_dict)
    text = comp.to_wcif_json(indent=2)
    assert "\n" in text
    assert json.loads(text) == sample_dict


def test_double_dict_round_trip_is_stable(sample_dict: dict[str, Any]) -> None:
    first = Competition.model_validate(sample_dict).to_wcif_dict()
    second = Competition.model_validate(first).to_wcif_dict()
    assert second == first
    assert first == sample_dict


def test_double_json_round_trip_is_stable(sample_competition: Competition) -> None:
    text = sample_competition.to_wcif_json(indent=2)
    again = Competition.model_validate_json(text).to_wcif_json(indent=2)
    assert again == text


# ---------------------------------------------------------------------------
# Specific data that must survive the round-trip
# ---------------------------------------------------------------------------


def test_competition_extension_survives(sample_dict: dict[str, Any]) -> None:
    doc = Competition.model_validate(sample_dict).to_wcif_dict()
    assert doc["extensions"] == sample_dict["extensions"]
    (ext,) = doc["extensions"]
    assert ext["id"] == "groupifier.CompetitionConfig"
    assert ext["data"] == {
        "localNamesFirst": False,
        "printOneName": True,
        "scorecardsBackgroundUrl": "",
        "competitorsSortingRule": "ranks",
        "noTasksForNewcomers": False,
        "tasksForOwnEventsOnly": False,
        "noRunningForForeigners": False,
        "printStations": True,
        "scorecardPaperSize": "a4",
    }


def test_activity_extension_survives(sample_dict: dict[str, Any]) -> None:
    doc = Competition.model_validate(sample_dict).to_wcif_dict()
    activity = _activity_dict(doc, 2)
    assert activity["activityCode"] == "333-r1"
    assert activity["extensions"] == [
        {
            "id": "groupifier.ActivityConfig",
            "specUrl": "https://groupifier.jonatanklosko.com/wcif-extensions/ActivityConfig.json",
            "data": {
                "capacity": 6,
                "groups": 2,
                "scramblers": 1,
                "runners": 0,
                "assignJudges": True,
            },
        }
    ]


def test_room_extension_survives(sample_dict: dict[str, Any]) -> None:
    doc = Competition.model_validate(sample_dict).to_wcif_dict()
    main_hall, side_room = doc["schedule"]["venues"][0]["rooms"]
    assert main_hall["name"] == "Main Hall"
    assert main_hall["extensions"] == [
        {
            "id": "groupifier.RoomConfig",
            "specUrl": "https://groupifier.jonatanklosko.com/wcif-extensions/RoomConfig.json",
            "data": {"capacity": 40},
        }
    ]
    assert side_room["name"] == "Side Room"
    assert side_room["extensions"] == []


def test_unknown_top_level_key_survives(sample_dict: dict[str, Any]) -> None:
    comp = Competition.model_validate(sample_dict)
    expected = {
        "source": "external-registration-form",
        "syncedAt": "2026-05-01T10:00:00Z",
        "paymentProvider": "manual",
    }
    assert comp.model_extra is not None
    assert comp.model_extra["registrationInfo"] == expected
    assert comp.to_wcif_dict()["registrationInfo"] == expected


def test_delegate_nulls_survive(sample_dict: dict[str, Any]) -> None:
    doc = Competition.model_validate(sample_dict).to_wcif_dict()
    delegate = _person_dict(doc, "Georgios Makris")
    assert "registrantId" in delegate
    assert delegate["registrantId"] is None
    assert "registration" in delegate
    assert delegate["registration"] is None
    assert delegate["roles"] == ["delegate"]
    assert delegate["wcaId"] == "2009MAKR01"


def test_first_timer_null_wca_id_survives(sample_dict: dict[str, Any]) -> None:
    doc = Competition.model_validate(sample_dict).to_wcif_dict()
    first_timer = _person_dict(doc, "Dimitris Vlachos")
    assert first_timer["registrantId"] == 1005
    assert "wcaId" in first_timer
    assert first_timer["wcaId"] is None
    assert first_timer["avatar"] is None


def test_email_and_birthdate_only_where_given(sample_dict: dict[str, Any]) -> None:
    doc = Competition.model_validate(sample_dict).to_wcif_dict()
    with_email = [p["name"] for p in doc["persons"] if "email" in p]
    with_birthdate = [p["name"] for p in doc["persons"] if "birthdate" in p]
    assert with_email == ["Eleni Konstantinou"]
    assert with_birthdate == ["Eleni Konstantinou"]
    eleni = _person_dict(doc, "Eleni Konstantinou")
    assert eleni["email"] == "eleni.konstantinou@example.com"
    assert eleni["birthdate"] == "1994-03-12"


def test_explicit_null_email_and_birthdate_are_kept(sample_dict: dict[str, Any]) -> None:
    nikolaos = _person_dict(sample_dict, "Nikolaos Papadakis")
    nikolaos["email"] = None
    nikolaos["birthdate"] = None
    doc = Competition.model_validate(sample_dict).to_wcif_dict()
    out = _person_dict(doc, "Nikolaos Papadakis")
    assert "email" in out
    assert out["email"] is None
    assert "birthdate" in out
    assert out["birthdate"] is None


def test_registration_guests_and_comments_only_where_given(sample_dict: dict[str, Any]) -> None:
    doc = Competition.model_validate(sample_dict).to_wcif_dict()
    registrations: dict[str, dict[str, Any]] = {
        p["name"]: p["registration"] for p in doc["persons"] if p["registration"] is not None
    }
    assert sorted(n for n, reg in registrations.items() if "guests" in reg) == ["Lukas Brandt"]
    assert sorted(n for n, reg in registrations.items() if "comments" in reg) == ["Lukas Brandt"]
    lukas = registrations["Lukas Brandt"]
    assert lukas["guests"] == 1
    assert lukas["comments"] == "Would prefer a seat away from the entrance."
    assert "administrativeNotes" not in lukas


def test_final_round_null_keys_survive(sample_dict: dict[str, Any]) -> None:
    doc = Competition.model_validate(sample_dict).to_wcif_dict()
    first, final = _event_dict(doc, "333")["rounds"]
    assert final["id"] == "333-r2"
    assert "cutoff" in final
    assert final["cutoff"] is None
    assert "advancementCondition" in final
    assert final["advancementCondition"] is None
    assert final["timeLimit"] == {"centiseconds": 60000, "cumulativeRoundIds": []}
    assert first["cutoff"] == {"numberOfAttempts": 2, "attemptResult": 3000}
    assert first["advancementCondition"] == {"type": "ranking", "level": 3}


def test_explicit_null_time_limit_is_kept(sample_dict: dict[str, Any]) -> None:
    _event_dict(sample_dict, "333")["rounds"][1]["timeLimit"] = None
    doc = Competition.model_validate(sample_dict).to_wcif_dict()
    final = _event_dict(doc, "333")["rounds"][1]
    assert "timeLimit" in final
    assert final["timeLimit"] is None


def test_mbld_packed_ints_unchanged(sample_dict: dict[str, Any]) -> None:
    doc = Competition.model_validate(sample_dict).to_wcif_dict()
    results = _event_dict(doc, "333mbf")["rounds"][0]["results"]
    assert [r["attempts"][0]["result"] for r in results] == [880325201, 930272001]
    assert [r["best"] for r in results] == [880325201, 930272001]
    mbf_bests = [
        pb["best"] for p in doc["persons"] for pb in p["personalBests"] if pb["eventId"] == "333mbf"
    ]
    assert mbf_bests == [880325201, 930272001]


def test_omittable_fields_absent_when_not_given(sample_dict: dict[str, Any]) -> None:
    doc = Competition.model_validate(sample_dict).to_wcif_dict()
    assert "series" not in doc
    assert doc["competitorLimit"] == 120

    event_333 = _event_dict(doc, "333")
    assert event_333["competitorLimit"] == 80
    assert "qualification" not in event_333

    event_333fm = _event_dict(doc, "333fm")
    assert "competitorLimit" not in event_333fm
    assert "qualification" not in event_333fm

    event_333mbf = _event_dict(doc, "333mbf")
    assert event_333mbf["qualification"] == {
        "whenDate": "2026-03-01",
        "type": "anyResult",
        "resultType": "single",
    }
    assert "level" not in event_333mbf["qualification"]

    for round_ in [r for e in doc["events"] for r in e["rounds"]]:
        assert "scrambleSets" not in round_

    assert "scrambleSets" not in doc["events"][0]["rounds"][0]


def test_reconstruction_only_on_attempt_that_had_one(sample_dict: dict[str, Any]) -> None:
    doc = Competition.model_validate(sample_dict).to_wcif_dict()
    with_reconstruction = [a for a in _all_attempts(doc) if "reconstruction" in a]
    assert with_reconstruction == [{"result": 1290, "reconstruction": RECONSTRUCTION}]


# ---------------------------------------------------------------------------
# Loading from different sources
# ---------------------------------------------------------------------------


def test_load_wcif_from_path_and_from_string(
    sample_path: Path, sample_dict: dict[str, Any]
) -> None:
    from pywcif.client import load_wcif

    from_path = load_wcif(sample_path)
    from_text = load_wcif(str(sample_path))

    assert from_path.id == "AthensOpen2026"
    assert from_path.to_wcif_dict() == sample_dict
    assert from_text.to_wcif_dict() == sample_dict


# ---------------------------------------------------------------------------
# Relational helpers
# ---------------------------------------------------------------------------


def test_get_person_by_registrant_id(sample_competition: Competition) -> None:
    person = sample_competition.get_person(registrant_id=1001)
    assert person is not None
    assert person.name == "Nikolaos Papadakis"
    assert person.wca_id == "2019PAPA01"


def test_get_person_by_wca_id(sample_competition: Competition) -> None:
    person = sample_competition.get_person(wca_id="2018BRAN03")
    assert person is not None
    assert person.name == "Lukas Brandt"
    assert person.registrant_id == 1003


def test_get_person_by_wca_user_id_finds_null_registrant(
    sample_competition: Competition,
) -> None:
    person = sample_competition.get_person(wca_user_id=4107)
    assert person is not None
    assert person.name == "Georgios Makris"
    assert person.registrant_id is None


def test_get_person_combined_criteria(sample_competition: Competition) -> None:
    both = sample_competition.get_person(registrant_id=1002, wca_user_id=4102)
    assert both is not None
    assert both.name == "Eleni Konstantinou"
    assert sample_competition.get_person(registrant_id=1002, wca_user_id=4101) is None
    assert sample_competition.get_person(registrant_id=1005, wca_id="2019PAPA01") is None


def test_get_person_not_found_and_no_criteria(sample_competition: Competition) -> None:
    assert sample_competition.get_person(registrant_id=9999) is None
    assert sample_competition.get_person(wca_id="XXXX99XX99") is None
    assert sample_competition.get_person() is None


def test_get_accepted_competitors_excludes_pending_and_delegate(
    sample_competition: Competition,
) -> None:
    names = [p.name for p in sample_competition.get_accepted_competitors()]
    assert names == [
        "Nikolaos Papadakis",
        "Eleni Konstantinou",
        "Lukas Brandt",
        "Ayaka Tanaka",
        "Dimitris Vlachos",
    ]
    assert "Chloe Martin" not in names
    assert "Georgios Makris" not in names


@pytest.mark.parametrize(
    ("event_id", "expected_ids"),
    [
        ("333", [1001, 1002, 1003, 1004, 1005]),
        ("333fm", [1001, 1002, 1004]),
        ("333mbf", [1001, 1003]),
        ("444", []),
    ],
)
def test_get_accepted_competitors_event_filter(
    sample_competition: Competition, event_id: str, expected_ids: list[int]
) -> None:
    people = sample_competition.get_accepted_competitors(event_id)
    assert [p.registrant_id for p in people] == expected_ids


def test_get_first_timers_is_dimitris(sample_competition: Competition) -> None:
    timers = sample_competition.get_first_timers()
    assert [(p.registrant_id, p.name) for p in timers] == [(1005, "Dimitris Vlachos")]


def test_get_staff_includes_delegate_and_organizer(sample_competition: Competition) -> None:
    staff = sample_competition.get_staff()
    assert [p.name for p in staff] == ["Eleni Konstantinou", "Georgios Makris"]


def test_get_event_and_missing_event(sample_competition: Competition) -> None:
    event = sample_competition.get_event("333")
    assert event is not None
    assert len(event.rounds) == 2
    assert event.competitor_limit == 80

    mbf = sample_competition.get_event("333mbf")
    assert mbf is not None
    assert mbf.qualification is not None
    assert mbf.qualification.when_date == "2026-03-01"

    assert sample_competition.get_event("999") is None


def test_get_round_and_missing_round(sample_competition: Competition) -> None:
    first = sample_competition.get_round("333-r1")
    assert first is not None
    assert first.format == "a"
    assert first.cutoff is not None
    assert first.cutoff.attempt_result == 3000
    assert first.advancement_condition is not None
    assert first.advancement_condition.level == 3

    final = sample_competition.get_round("333-r2")
    assert final is not None
    assert final.cutoff is None
    assert final.advancement_condition is None

    fm = sample_competition.get_round("333fm-r1")
    assert fm is not None
    assert fm.format == "m"

    assert sample_competition.get_round("333-r9") is None


def test_iter_activities_counts_with_and_without_children(
    sample_competition: Competition,
) -> None:
    everything = [activity.id for _, _, activity in sample_competition.iter_activities()]
    assert everything == [1, 2, 3, 4, 5, 10, 11, 6, 7, 8, 9]
    top_level = [
        activity.id for _, _, activity in sample_competition.iter_activities(include_children=False)
    ]
    assert top_level == [1, 2, 5, 10, 6, 8]


def test_get_activity_child_returns_right_room(sample_competition: Competition) -> None:
    main = sample_competition.get_activity(3)
    assert main is not None
    venue, room, activity = main
    assert venue.name == "Athens Open Venue"
    assert room.name == "Main Hall"
    assert activity.activity_code == "333-r1-g1"

    side = sample_competition.get_activity(7)
    assert side is not None
    assert side[1].name == "Side Room"
    assert side[2].activity_code == "333fm-r1-g1"

    top = sample_competition.get_activity(10)
    assert top is not None
    assert top[1].name == "Main Hall"

    assert sample_competition.get_activity(999) is None


def test_get_person_schedule_local_time_and_order(sample_competition: Competition) -> None:
    entries = sample_competition.get_person_schedule(1001)
    assert [e.activity.id for e in entries] == [3, 7, 9, 11]

    first = entries[0]
    assert first.activity.start_time == "2026-05-16T06:30:00Z"
    assert first.local_start.hour == 9
    assert first.local_start.utcoffset() == timedelta(hours=3)
    assert first.local_start.isoformat() == "2026-05-16T09:30:00+03:00"
    assert first.local_end.isoformat() == "2026-05-16T10:30:00+03:00"
    zone = first.local_start.tzinfo
    assert isinstance(zone, ZoneInfo)
    assert zone.key == "Europe/Athens"
    assert first.room.name == "Main Hall"
    assert first.venue.name == "Athens Open Venue"
    assert first.assignment.assignment_code == "competitor"

    assert entries[1].room.name == "Side Room"
    assert entries[1].local_start.isoformat() == "2026-05-16T11:30:00+03:00"
    assert entries[3].local_start.isoformat() == "2026-05-16T15:30:00+03:00"


def test_get_person_schedule_sorts_by_local_start(sample_competition: Competition) -> None:
    person = sample_competition.get_person(registrant_id=1001)
    assert person is not None
    person.assignments.reverse()
    ids = [e.activity.id for e in sample_competition.get_person_schedule(1001)]
    assert ids == [3, 7, 9, 11]


def test_get_person_schedule_skips_unknown_activity(sample_competition: Competition) -> None:
    person = sample_competition.get_person(registrant_id=1001)
    assert person is not None
    person.assignments.append(Assignment(activity_id=424242, assignment_code="competitor"))
    ids = [e.activity.id for e in sample_competition.get_person_schedule(1001)]
    assert ids == [3, 7, 9, 11]


def test_get_person_schedule_unknown_person_is_empty(sample_competition: Competition) -> None:
    assert sample_competition.get_person_schedule(999) == []


# ---------------------------------------------------------------------------
# Decoding fixture results
# ---------------------------------------------------------------------------


def test_format_mbld_results_from_fixture(sample_dict: dict[str, Any]) -> None:
    mbf_pb = [
        pb
        for pb in _person_dict(sample_dict, "Nikolaos Papadakis")["personalBests"]
        if pb["eventId"] == "333mbf"
    ]
    assert format_result(mbf_pb[0]["best"], "333mbf") == "12/13 54:12"
    assert format_result(930272001, "333mbf") == "7/8 45:20"


def test_multi_blind_fields_decoded() -> None:
    result = MultiBlindResult.from_wcif_int(880325201)
    assert (result.solved, result.attempted, result.time_seconds) == (12, 13, 3252)
    assert result.missed == 1
    assert result.points == 11
    assert result.is_old_style is False


def test_format_fmc_single_and_mean_from_fixture(sample_dict: dict[str, Any]) -> None:
    fm_round = _event_dict(sample_dict, "333fm")["rounds"][0]
    averages = [format_result(r["average"], "333fm", is_average=True) for r in fm_round["results"]]
    assert averages == ["24.33", "28.33", "DNF"]
    singles = [format_result(r["best"], "333fm") for r in fm_round["results"]]
    assert singles == ["22", "26", "30"]
    assert format_result(3000, "333fm", is_average=True) == "30.00"


def test_format_standard_event_attempts_from_fixture(sample_dict: dict[str, Any]) -> None:
    vlachos = next(
        r for r in _event_dict(sample_dict, "333")["rounds"][0]["results"] if r["personId"] == 1005
    )
    formatted = [format_result(a["result"], "333") for a in vlachos["attempts"]]
    assert formatted == ["18.90", "DNF", "17.25", "20.10", "19.66"]
    assert format_result(vlachos["average"], "333", is_average=True) == "19.55"
    assert format_result(0, "333") == ""
