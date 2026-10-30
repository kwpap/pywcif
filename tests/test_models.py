"""Tests for the WCIF v1.2 Pydantic models, enums and Competition helpers."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from pywcif.activity_code import ActivityCode
from pywcif.enums import (
    AdvancementType,
    AssignmentCode,
    EventId,
    Gender,
    QualificationType,
    RegistrationStatus,
    ResultType,
    Role,
    RoundFormat,
)
from pywcif.models import (
    Activity,
    AdvancementCondition,
    Assignment,
    Attempt,
    Competition,
    Cutoff,
    Event,
    Person,
    PersonalBest,
    Qualification,
    Registration,
    Result,
    Round,
    TimeLimit,
    Venue,
)


def _activity(
    activity_id: int,
    code: str,
    start: str,
    end: str,
    children: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": activity_id,
        "name": f"Activity {activity_id}",
        "activityCode": code,
        "startTime": start,
        "endTime": end,
    }
    if children is not None:
        payload["childActivities"] = children
    return payload


def _competition_payload() -> dict[str, Any]:
    """A small but complete WCIF document with two venues, nested activities and staff."""
    return {
        "formatVersion": "1.0",
        "id": "TestOpen2024",
        "name": "Test Open 2024",
        "shortName": "Test Open",
        "competitorLimit": 100,
        "persons": [
            {
                "registrantId": 1,
                "name": "Alice Competitor",
                "wcaUserId": 101,
                "wcaId": "2010ABCD01",
                "countryIso2": "GR",
                "gender": "f",
                "avatar": None,
                "roles": [],
                "registration": {
                    "wcaRegistrationId": 1,
                    "eventIds": ["333", "333fm"],
                    "status": "accepted",
                    "isCompeting": True,
                },
                "assignments": [
                    {"activityId": 102, "assignmentCode": "competitor"},
                    {"activityId": 999, "assignmentCode": "competitor"},
                    {"activityId": 300, "assignmentCode": "competitor"},
                ],
                "personalBests": [],
                "extensions": [],
            },
            {
                "registrantId": 2,
                "name": "Bob Judge",
                "wcaUserId": 102,
                "wcaId": "2012JUDG01",
                "countryIso2": "US",
                "gender": "m",
                "avatar": None,
                "roles": [],
                "registration": None,
                "assignments": [
                    {"activityId": 400, "assignmentCode": "judge"},
                    {"activityId": 101, "assignmentCode": "staff-judge", "stationNumber": 2},
                ],
                "personalBests": [],
                "extensions": [],
            },
            {
                "registrantId": 3,
                "name": "Carol FirstTimer",
                "wcaUserId": 103,
                "wcaId": None,
                "countryIso2": "DE",
                "gender": "f",
                "avatar": None,
                "roles": [],
                "registration": {
                    "wcaRegistrationId": 3,
                    "eventIds": ["333"],
                    "status": "accepted",
                    "isCompeting": True,
                },
                "assignments": [],
                "personalBests": [],
                "extensions": [],
            },
            {
                "registrantId": None,
                "name": "Dan Delegate",
                "wcaUserId": 104,
                "wcaId": "2005DELE01",
                "countryIso2": "GR",
                "gender": "m",
                "avatar": None,
                "roles": ["delegate"],
                "registration": None,
                "assignments": [],
                "personalBests": [],
                "extensions": [],
            },
            {
                "registrantId": 5,
                "name": "Eve Pending",
                "wcaUserId": 105,
                "wcaId": "2011XYZ01",
                "countryIso2": "FR",
                "gender": "f",
                "avatar": None,
                "roles": [],
                "registration": {
                    "wcaRegistrationId": 5,
                    "eventIds": ["333"],
                    "status": "pending",
                    "isCompeting": True,
                },
                "assignments": [],
                "personalBests": [],
                "extensions": [],
            },
            {
                "registrantId": 6,
                "name": "Frank Spectator",
                "wcaUserId": 106,
                "wcaId": "2013SPEC01",
                "countryIso2": "FR",
                "gender": "m",
                "avatar": None,
                "roles": [],
                "registration": {
                    "wcaRegistrationId": 6,
                    "eventIds": ["333"],
                    "status": "accepted",
                    "isCompeting": False,
                },
                "assignments": [],
                "personalBests": [],
                "extensions": [],
            },
        ],
        "events": [
            {
                "id": "333",
                "rounds": [
                    {
                        "id": "333-r1",
                        "format": "a",
                        "timeLimit": {"centiseconds": 60000, "cumulativeRoundIds": []},
                        "cutoff": {"numberOfAttempts": 2, "attemptResult": 3000},
                        "advancementCondition": {"type": "percent", "level": 75},
                        "results": [],
                        "scrambleSetCount": 1,
                        "extensions": [],
                    },
                    {
                        "id": "333-r2",
                        "format": "a",
                        "timeLimit": None,
                        "cutoff": None,
                        "advancementCondition": None,
                        "results": [],
                        "scrambleSetCount": 1,
                        "extensions": [],
                    },
                ],
                "extensions": [],
            },
            {
                "id": "333fm",
                "rounds": [
                    {
                        "id": "333fm-r1",
                        "format": "m",
                        "results": [],
                        "scrambleSetCount": 1,
                        "extensions": [],
                    }
                ],
                "extensions": [],
            },
        ],
        "schedule": {
            "startDate": "2024-07-26",
            "numberOfDays": 2,
            "venues": [
                {
                    "id": 1,
                    "name": "Athens Venue",
                    "latitudeMicrodegrees": 37983810,
                    "longitudeMicrodegrees": 23727539,
                    "countryIso2": "GR",
                    "timezone": "Europe/Athens",
                    "rooms": [
                        {
                            "id": 10,
                            "name": "Main Hall",
                            "color": "#ff0000",
                            "activities": [
                                _activity(
                                    100,
                                    "333-r1",
                                    "2024-07-26T07:00:00Z",
                                    "2024-07-26T08:00:00Z",
                                    children=[
                                        _activity(
                                            101,
                                            "333-r1-g1",
                                            "2024-07-26T07:00:00Z",
                                            "2024-07-26T07:30:00Z",
                                        ),
                                        _activity(
                                            102,
                                            "333-r1-g2",
                                            "2024-07-26T07:30:00Z",
                                            "2024-07-26T08:00:00Z",
                                        ),
                                    ],
                                ),
                                _activity(
                                    200,
                                    "other-lunch",
                                    "2024-07-26T09:00:00Z",
                                    "2024-07-26T10:00:00Z",
                                ),
                            ],
                            "extensions": [],
                        },
                        {
                            "id": 20,
                            "name": "Side Room",
                            "color": "#00ff00",
                            "activities": [
                                _activity(
                                    300,
                                    "333fm-r1",
                                    "2024-07-26T06:00:00Z",
                                    "2024-07-26T06:30:00Z",
                                ),
                            ],
                            "extensions": [],
                        },
                    ],
                    "extensions": [],
                },
                {
                    "id": 2,
                    "name": "New York Venue",
                    "latitudeMicrodegrees": 40712776,
                    "longitudeMicrodegrees": -74005974,
                    "countryIso2": "US",
                    "timezone": "America/New_York",
                    "rooms": [
                        {
                            "id": 30,
                            "name": "Hall NY",
                            "color": "#0000ff",
                            "activities": [
                                _activity(
                                    400,
                                    "333-r2",
                                    "2024-07-26T13:00:00Z",
                                    "2024-07-26T14:00:00Z",
                                ),
                            ],
                            "extensions": [],
                        }
                    ],
                    "extensions": [],
                },
            ],
        },
        "extensions": [],
    }


@pytest.fixture
def comp() -> Competition:
    return Competition.model_validate(_competition_payload())


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


def test_enum_members_compare_equal_to_raw_strings() -> None:
    assert EventId.E333.value == "333"
    assert EventId.E333FM.value == "333fm"
    assert RoundFormat.AVERAGE.value == "a"
    assert RoundFormat.MEAN.value == "m"
    assert AdvancementType.ATTEMPT_RESULT.value == "attemptResult"
    assert AssignmentCode.STAFF_DATAENTRY.value == "staff-dataentry"
    assert RegistrationStatus.WAITING_LIST.value == "waiting_list"
    assert QualificationType.ANY_RESULT.value == "anyResult"
    assert ResultType.AVERAGE.value == "average"
    assert Role.TRAINEE_DELEGATE.value == "trainee-delegate"
    assert Gender.F.value == "f"


def test_enum_str_returns_raw_value() -> None:
    assert str(EventId.E333BF) == "333bf"
    assert str(RegistrationStatus.ACCEPTED) == "accepted"
    assert f"{AssignmentCode.JUDGE}" == "judge"


def test_enum_values_are_str_instances() -> None:
    assert isinstance(EventId.CLOCK, str)


# ---------------------------------------------------------------------------
# camelCase parsing and dumping
# ---------------------------------------------------------------------------


def test_camel_case_keys_parse_into_snake_case_attributes(comp: Competition) -> None:
    assert comp.short_name == "Test Open"
    assert comp.format_version == "1.0"
    assert comp.schedule.number_of_days == 2
    venue = comp.schedule.venues[0]
    assert venue.country_iso2 == "GR"
    assert venue.latitude_microdegrees == 37983810
    assert venue.longitude_microdegrees == 23727539
    assert comp.persons[0].wca_user_id == 101
    assert comp.persons[0].country_iso2 == "GR"
    assert comp.persons[0].registration is not None
    assert comp.persons[0].registration.event_ids == ["333", "333fm"]


def test_camel_case_keys_are_dumped(comp: Competition) -> None:
    data = comp.to_wcif_dict()
    assert data["shortName"] == "Test Open"
    assert data["schedule"]["numberOfDays"] == 2
    venue = data["schedule"]["venues"][0]
    assert venue["countryIso2"] == "GR"
    assert venue["latitudeMicrodegrees"] == 37983810
    assert venue["longitudeMicrodegrees"] == 23727539
    assert "country_iso2" not in venue
    assert data["persons"][0]["wcaUserId"] == 101
    assert data["persons"][0]["registration"]["wcaRegistrationId"] == 1
    assert data["persons"][0]["registration"]["isCompeting"] is True


def test_snake_case_names_are_accepted_by_populate_by_name() -> None:
    venue = Venue(
        id=1,
        name="V",
        latitude_microdegrees=1,
        longitude_microdegrees=2,
        country_iso2="GR",
        timezone="Europe/Athens",
    )
    assert venue.latitude_microdegrees == 1
    assert venue.to_wcif_dict()["latitudeMicrodegrees"] == 1


def test_nested_activity_children_are_dumped_camel_case() -> None:
    activity = Activity.model_validate(
        _activity(
            1,
            "333-r1",
            "2024-07-26T07:00:00Z",
            "2024-07-26T08:00:00Z",
            children=[_activity(2, "333-r1-g1", "2024-07-26T07:00:00Z", "2024-07-26T07:30:00Z")],
        )
    )
    assert isinstance(activity.child_activities[0], Activity)
    dumped = activity.to_wcif_dict()
    assert dumped["activityCode"] == "333-r1"
    assert dumped["childActivities"][0]["activityCode"] == "333-r1-g1"
    assert "scrambleSetId" not in dumped["childActivities"][0]


def test_qualification_accepts_when_date_camel_case() -> None:
    qual = Qualification.model_validate(
        {"whenDate": "2024-01-01", "type": "ranking", "resultType": "single"}
    )
    assert qual.when_date == "2024-01-01"
    assert qual.to_wcif_dict()["whenDate"] == "2024-01-01"


def test_qualification_accepts_legacy_when_key() -> None:
    qual = Qualification.model_validate(
        {"when": "2023-06-30", "type": "attemptResult", "resultType": "average", "level": 1000}
    )
    assert qual.when_date == "2023-06-30"
    dumped = qual.to_wcif_dict()
    assert dumped["whenDate"] == "2023-06-30"
    assert "when" not in dumped


def test_qualification_accepts_snake_case_when_date() -> None:
    qual = Qualification(when_date="2024-02-02", type="ranking", result_type="single")
    assert qual.when_date == "2024-02-02"
    assert qual.to_wcif_dict()["whenDate"] == "2024-02-02"


def test_qualification_dumps_when_date_inside_competition() -> None:
    payload = _competition_payload()
    payload["events"][0]["qualification"] = {
        "when": "2024-01-15",
        "type": "ranking",
        "resultType": "single",
        "level": 50,
    }
    dumped = Competition.model_validate(payload).to_wcif_dict()
    qualification = dumped["events"][0]["qualification"]
    assert qualification == {
        "whenDate": "2024-01-15",
        "type": "ranking",
        "resultType": "single",
        "level": 50,
    }


def test_person_accepts_snake_case_and_camel_case_equally() -> None:
    camel = Person.model_validate(
        {"name": "A", "wcaUserId": 1, "countryIso2": "GR", "gender": "m", "wcaId": None}
    )
    snake = Person(name="A", wca_user_id=1, country_iso2="GR", gender="m", wca_id=None)
    assert camel.to_wcif_dict() == snake.to_wcif_dict()


# ---------------------------------------------------------------------------
# Extra keys
# ---------------------------------------------------------------------------


def test_unknown_top_level_keys_survive_dump() -> None:
    payload = _competition_payload()
    payload["futureKey"] = {"nested": [1, 2, 3]}
    comp = Competition.model_validate(payload)
    assert comp.to_wcif_dict()["futureKey"] == {"nested": [1, 2, 3]}


def test_unknown_nested_keys_survive_dump() -> None:
    payload = _competition_payload()
    payload["persons"][0]["x-groupifier-tag"] = "vip"
    payload["schedule"]["venues"][0]["rooms"][0]["activities"][0]["x-note"] = 7
    dumped = Competition.model_validate(payload).to_wcif_dict()
    assert dumped["persons"][0]["x-groupifier-tag"] == "vip"
    assert dumped["schedule"]["venues"][0]["rooms"][0]["activities"][0]["x-note"] == 7


def test_unknown_keys_on_third_party_extension_survive_dump() -> None:
    payload = _competition_payload()
    payload["extensions"] = [
        {
            "id": "org.example.tool",
            "specUrl": "https://example.org/spec",
            "data": {"enabled": True, "rounds": {"a": 1}},
        }
    ]
    dumped = Competition.model_validate(payload).to_wcif_dict()
    assert dumped["extensions"] == payload["extensions"]


# ---------------------------------------------------------------------------
# Unknown enum strings
# ---------------------------------------------------------------------------


def test_unknown_event_id_is_accepted() -> None:
    event = Event.model_validate({"id": "fto"})
    assert event.id == "fto"
    assert event.to_wcif_dict()["id"] == "fto"


def test_unknown_registration_status_is_accepted() -> None:
    registration = Registration.model_validate(
        {"wcaRegistrationId": 9, "eventIds": ["333"], "status": "withdrawn"}
    )
    assert registration.status == "withdrawn"
    assert registration.to_wcif_dict()["status"] == "withdrawn"


def test_waiting_list_status_is_accepted() -> None:
    registration = Registration.model_validate(
        {"wcaRegistrationId": 9, "eventIds": ["333"], "status": "waiting_list"}
    )
    assert registration.status == RegistrationStatus.WAITING_LIST


def test_custom_assignment_code_is_accepted() -> None:
    assignment = Assignment.model_validate({"activityId": 1, "assignmentCode": "staff-foo"})
    assert assignment.assignment_code == "staff-foo"
    assert assignment.to_wcif_dict() == {
        "activityId": 1,
        "assignmentCode": "staff-foo",
        "stationNumber": None,
    }


def test_unknown_role_and_gender_are_accepted() -> None:
    person = Person.model_validate(
        {
            "name": "X",
            "wcaUserId": 1,
            "countryIso2": "GR",
            "gender": "x",
            "roles": ["observer", "organizer"],
        }
    )
    assert person.gender == "x"
    assert person.roles == ["observer", "organizer"]


def test_unknown_round_format_and_advancement_type_are_accepted() -> None:
    round_ = Round.model_validate(
        {
            "id": "333-r1",
            "format": "q",
            "advancementCondition": {"type": "custom", "level": 4},
        }
    )
    assert round_.format == "q"
    assert round_.advancement_condition is not None
    assert round_.advancement_condition.type == "custom"


def test_unknown_personal_best_type_is_accepted() -> None:
    best = PersonalBest.model_validate(
        {
            "eventId": "333",
            "best": 1000,
            "worldRanking": 1,
            "continentalRanking": 1,
            "nationalRanking": 1,
            "type": "mean",
        }
    )
    assert best.type == "mean"


def test_known_enum_values_are_dumped_as_plain_strings() -> None:
    event = Event(id=EventId.E333FM, rounds=[])
    dumped = event.to_wcif_dict()
    assert dumped["id"] == "333fm"
    assert type(dumped["id"]) is str


def test_enum_instances_in_round_format_are_dumped_as_strings() -> None:
    round_ = Round(id="333-r1", format=RoundFormat.AVERAGE)
    assert round_.to_wcif_dict()["format"] == "a"
    assert type(round_.to_wcif_dict()["format"]) is str


# ---------------------------------------------------------------------------
# Omittable fields
# ---------------------------------------------------------------------------


def _bare_person() -> dict[str, Any]:
    return {"name": "P", "wcaUserId": 1, "countryIso2": "GR", "gender": "f"}


def test_person_email_and_birthdate_omitted_when_absent() -> None:
    dumped = Person.model_validate(_bare_person()).to_wcif_dict()
    assert "email" not in dumped
    assert "birthdate" not in dumped


def test_person_email_kept_when_explicitly_null() -> None:
    payload = _bare_person() | {"email": None}
    dumped = Person.model_validate(payload).to_wcif_dict()
    assert "email" in dumped
    assert dumped["email"] is None


def test_person_email_kept_when_set() -> None:
    dumped = Person.model_validate(_bare_person() | {"email": "a@example.org"}).to_wcif_dict()
    assert dumped["email"] == "a@example.org"


def test_person_email_omitted_when_none_passed_in_python_and_not_set() -> None:
    person = Person(name="P", wca_user_id=1, country_iso2="GR", gender="f")
    assert "email" not in person.to_wcif_dict()


def test_registration_optional_fields_omitted_when_absent() -> None:
    dumped = Registration.model_validate(
        {"wcaRegistrationId": 1, "eventIds": ["333"], "status": "accepted"}
    ).to_wcif_dict()
    assert "guests" not in dumped
    assert "comments" not in dumped
    assert "administrativeNotes" not in dumped


def test_registration_optional_fields_kept_when_null() -> None:
    dumped = Registration.model_validate(
        {
            "wcaRegistrationId": 1,
            "eventIds": ["333"],
            "status": "accepted",
            "guests": None,
            "comments": None,
            "administrativeNotes": None,
        }
    ).to_wcif_dict()
    assert dumped["guests"] is None
    assert dumped["comments"] is None
    assert dumped["administrativeNotes"] is None


def test_registration_optional_fields_kept_when_set() -> None:
    dumped = Registration.model_validate(
        {
            "wcaRegistrationId": 1,
            "eventIds": ["333"],
            "status": "accepted",
            "guests": 2,
            "comments": "vegetarian",
            "administrativeNotes": "paid",
        }
    ).to_wcif_dict()
    assert dumped["guests"] == 2
    assert dumped["comments"] == "vegetarian"
    assert dumped["administrativeNotes"] == "paid"


def test_attempt_reconstruction_omitted_when_absent() -> None:
    assert Attempt(result=1234).to_wcif_dict() == {"result": 1234}


def test_attempt_reconstruction_kept_when_explicitly_null() -> None:
    attempt = Attempt.model_validate({"result": 1234, "reconstruction": None})
    assert attempt.to_wcif_dict() == {"result": 1234, "reconstruction": None}


def test_attempt_reconstruction_kept_when_set() -> None:
    attempt = Attempt.model_validate({"result": 1234, "reconstruction": "R U F"})
    assert attempt.to_wcif_dict() == {"result": 1234, "reconstruction": "R U F"}


def test_round_scramble_sets_omitted_when_absent() -> None:
    round_ = Round.model_validate({"id": "333-r1", "format": "3"})
    assert "scrambleSets" not in round_.to_wcif_dict()


def test_round_scramble_sets_kept_when_null() -> None:
    round_ = Round.model_validate({"id": "333-r1", "format": "3", "scrambleSets": None})
    assert round_.to_wcif_dict()["scrambleSets"] is None


def test_round_scramble_sets_kept_when_set() -> None:
    round_ = Round.model_validate({"id": "333-r1", "format": "3", "scrambleSets": [{"id": 1}]})
    assert round_.to_wcif_dict()["scrambleSets"] == [{"id": 1}]


def test_event_competitor_limit_and_qualification_omitted_when_absent() -> None:
    dumped = Event.model_validate({"id": "333"}).to_wcif_dict()
    assert "competitorLimit" not in dumped
    assert "qualification" not in dumped


def test_event_competitor_limit_and_qualification_kept_when_null() -> None:
    dumped = Event.model_validate(
        {"id": "333", "competitorLimit": None, "qualification": None}
    ).to_wcif_dict()
    assert dumped["competitorLimit"] is None
    assert dumped["qualification"] is None


def test_qualification_level_omitted_when_absent() -> None:
    qual = Qualification.model_validate(
        {"whenDate": "2024-01-01", "type": "anyResult", "resultType": "single"}
    )
    assert "level" not in qual.to_wcif_dict()


def test_qualification_level_kept_when_null() -> None:
    qual = Qualification.model_validate(
        {"whenDate": "2024-01-01", "type": "anyResult", "resultType": "single", "level": None}
    )
    assert qual.to_wcif_dict()["level"] is None


def test_competition_series_omitted_when_absent() -> None:
    comp = Competition.model_validate(_competition_payload())
    assert "series" not in comp.to_wcif_dict()


def test_competition_series_kept_when_null() -> None:
    payload = _competition_payload() | {"series": None}
    assert Competition.model_validate(payload).to_wcif_dict()["series"] is None


def test_competition_series_kept_when_set() -> None:
    payload = _competition_payload() | {"series": {"id": "gp-2024", "name": "GP"}}
    assert Competition.model_validate(payload).to_wcif_dict()["series"] == {
        "id": "gp-2024",
        "name": "GP",
    }


def test_omittable_fields_are_dropped_for_nested_models_in_whole_competition() -> None:
    payload = _competition_payload()
    payload["persons"][0]["registration"]["comments"] = None
    payload["events"][0]["rounds"][0]["results"] = [
        {
            "personId": 1,
            "best": 1000,
            "average": 1100,
            "attempts": [{"result": 1000}, {"result": 1200, "reconstruction": None}],
        }
    ]
    payload["events"][0]["qualification"] = {
        "whenDate": "2024-01-01",
        "type": "ranking",
        "resultType": "single",
    }
    dumped = Competition.model_validate(payload).to_wcif_dict()

    person = dumped["persons"][0]
    assert "email" not in person
    assert "birthdate" not in person
    assert "guests" not in person["registration"]
    assert "administrativeNotes" not in person["registration"]
    assert person["registration"]["comments"] is None

    round_ = dumped["events"][0]["rounds"][0]
    assert "scrambleSets" not in round_
    result = round_["results"][0]
    assert "reconstruction" not in result["attempts"][0]
    assert result["attempts"][1]["reconstruction"] is None

    event = dumped["events"][0]
    assert "competitorLimit" not in event
    assert "level" not in event["qualification"]
    assert "series" not in dumped


def test_explicit_nulls_survive_in_whole_competition_dump() -> None:
    payload = _competition_payload()
    payload["persons"][0]["email"] = None
    payload["events"][0]["competitorLimit"] = None
    payload["series"] = None
    dumped = Competition.model_validate(payload).to_wcif_dict()
    assert dumped["persons"][0]["email"] is None
    assert dumped["events"][0]["competitorLimit"] is None
    assert dumped["series"] is None


# ---------------------------------------------------------------------------
# Required-nullable fields
# ---------------------------------------------------------------------------


def test_person_required_nullable_fields_always_emitted() -> None:
    dumped = Person.model_validate(_bare_person()).to_wcif_dict()
    assert "registrantId" in dumped
    assert dumped["registrantId"] is None
    assert "wcaId" in dumped
    assert dumped["wcaId"] is None
    assert "avatar" in dumped
    assert dumped["avatar"] is None
    assert "registration" in dumped
    assert dumped["registration"] is None


def test_round_required_nullable_fields_always_emitted() -> None:
    dumped = Round.model_validate({"id": "333-r1", "format": "3"}).to_wcif_dict()
    assert dumped["timeLimit"] is None
    assert dumped["cutoff"] is None
    assert dumped["advancementCondition"] is None


def test_competition_competitor_limit_always_emitted() -> None:
    payload = _competition_payload()
    del payload["competitorLimit"]
    assert Competition.model_validate(payload).to_wcif_dict()["competitorLimit"] is None


def test_assignment_station_number_always_emitted() -> None:
    assert Assignment.model_validate(
        {"activityId": 1, "assignmentCode": "competitor"}
    ).to_wcif_dict() == {"activityId": 1, "assignmentCode": "competitor", "stationNumber": None}


def test_activity_scramble_set_id_omitted_when_absent() -> None:
    # The live WCA website leaves scrambleSetId out entirely, so it must not be added back.
    activity = Activity.model_validate(
        _activity(1, "333", "2024-07-26T07:00:00Z", "2024-07-26T08:00:00Z")
    )
    assert "scrambleSetId" not in activity.to_wcif_dict()


@pytest.mark.parametrize("value", [None, 7])
def test_activity_scramble_set_id_kept_when_given(value: int | None) -> None:
    payload = _activity(1, "333", "2024-07-26T07:00:00Z", "2024-07-26T08:00:00Z")
    payload["scrambleSetId"] = value
    assert Activity.model_validate(payload).to_wcif_dict()["scrambleSetId"] == value


def test_result_ranking_always_emitted() -> None:
    result = Result.model_validate({"personId": 1, "best": -1, "average": -1})
    dumped = result.to_wcif_dict()
    assert "ranking" in dumped
    assert dumped["ranking"] is None


def test_required_nullable_fields_emitted_as_null_in_nested_competition() -> None:
    payload: dict[str, Any] = {
        "id": "Mini",
        "name": "Mini",
        "shortName": "Mini",
        "schedule": {
            "startDate": "2024-01-01",
            "numberOfDays": 1,
            "venues": [
                {
                    "id": 1,
                    "name": "V",
                    "latitudeMicrodegrees": 0,
                    "longitudeMicrodegrees": 0,
                    "countryIso2": "GR",
                    "timezone": "UTC",
                    "rooms": [
                        {
                            "id": 1,
                            "name": "R",
                            "color": "#000",
                            "activities": [
                                {
                                    "id": 1,
                                    "name": "A",
                                    "activityCode": "333",
                                    "startTime": "2024-01-01T10:00:00Z",
                                    "endTime": "2024-01-01T11:00:00Z",
                                }
                            ],
                        }
                    ],
                }
            ],
        },
        "events": [{"id": "333", "rounds": [{"id": "333-r1", "format": "3"}]}],
        "persons": [
            {
                "name": "P",
                "wcaUserId": 1,
                "countryIso2": "GR",
                "gender": "m",
                "assignments": [{"activityId": 1, "assignmentCode": "judge"}],
            }
        ],
    }
    dumped = Competition.model_validate(payload).to_wcif_dict()
    assert dumped["competitorLimit"] is None
    assert dumped["persons"][0]["registrantId"] is None
    assert dumped["persons"][0]["wcaId"] is None
    assert dumped["persons"][0]["assignments"][0]["stationNumber"] is None
    assert dumped["events"][0]["rounds"][0]["timeLimit"] is None
    assert dumped["events"][0]["rounds"][0]["cutoff"] is None
    assert dumped["events"][0]["rounds"][0]["advancementCondition"] is None
    assert "scrambleSetId" not in dumped["schedule"]["venues"][0]["rooms"][0]["activities"][0]


def test_person_registrant_id_null_is_accepted() -> None:
    person = Person.model_validate(_bare_person() | {"registrantId": None})
    assert person.registrant_id is None


def test_missing_required_field_raises() -> None:
    with pytest.raises(ValidationError):
        Person.model_validate({"name": "no user id", "countryIso2": "GR", "gender": "f"})


# ---------------------------------------------------------------------------
# Serialization of WCIF JSON
# ---------------------------------------------------------------------------


def test_to_wcif_json_indent_round_trips_to_same_dict(comp: Competition) -> None:
    text = comp.to_wcif_json(indent=2)
    assert "\n" in text
    assert json.loads(text) == comp.to_wcif_dict()


def test_to_wcif_json_round_trips_through_model(comp: Competition) -> None:
    reloaded = Competition.model_validate_json(comp.to_wcif_json(indent=2))
    assert reloaded.to_wcif_dict() == comp.to_wcif_dict()


def test_to_wcif_json_default_is_compact(comp: Competition) -> None:
    text = comp.to_wcif_json()
    assert "\n" not in text
    assert json.loads(text) == comp.to_wcif_dict()


def test_to_wcif_dict_round_trips_without_changes() -> None:
    payload = _competition_payload()
    dumped = Competition.model_validate(payload).to_wcif_dict()
    assert Competition.model_validate(dumped).to_wcif_dict() == dumped


def test_to_wcif_dict_is_json_compatible(comp: Competition) -> None:
    assert json.loads(json.dumps(comp.to_wcif_dict())) == comp.to_wcif_dict()


# ---------------------------------------------------------------------------
# Activity properties
# ---------------------------------------------------------------------------


def test_parsed_code_returns_activity_code() -> None:
    activity = Activity.model_validate(
        _activity(1, "333-r1-g2-a1", "2024-07-26T07:00:00Z", "2024-07-26T08:00:00Z")
    )
    code = activity.parsed_code
    assert isinstance(code, ActivityCode)
    assert code == ActivityCode(event_id="333", round_number=1, group_number=2, attempt_number=1)


def test_parsed_code_for_non_competition_activity() -> None:
    activity = Activity.model_validate(
        _activity(1, "other-lunch", "2024-07-26T09:00:00Z", "2024-07-26T10:00:00Z")
    )
    assert activity.parsed_code.event_id == "other-lunch"
    assert activity.parsed_code.round_number is None


def test_parsed_code_raises_for_invalid_code() -> None:
    activity = Activity.model_validate(
        _activity(1, "333-g1-r1", "2024-07-26T09:00:00Z", "2024-07-26T10:00:00Z")
    )
    with pytest.raises(ValueError):
        _ = activity.parsed_code


def test_start_dt_parses_trailing_z_as_utc() -> None:
    activity = Activity.model_validate(
        _activity(1, "333", "2024-07-26T07:00:00Z", "2024-07-26T08:00:00Z")
    )
    assert activity.start_dt == datetime(2024, 7, 26, 7, 0, tzinfo=timezone.utc)
    assert activity.start_dt.utcoffset() == timedelta(0)


def test_end_dt_parses_trailing_z_as_utc() -> None:
    activity = Activity.model_validate(
        _activity(1, "333", "2024-07-26T07:00:00Z", "2024-07-26T08:30:00Z")
    )
    assert activity.end_dt == datetime(2024, 7, 26, 8, 30, tzinfo=timezone.utc)


def test_start_dt_converts_offset_to_utc() -> None:
    activity = Activity.model_validate(
        _activity(1, "333", "2024-07-26T10:00:00+03:00", "2024-07-26T11:00:00+03:00")
    )
    assert activity.start_dt == datetime(2024, 7, 26, 7, 0, tzinfo=timezone.utc)
    assert activity.start_dt.utcoffset() == timedelta(0)
    assert activity.end_dt == datetime(2024, 7, 26, 8, 0, tzinfo=timezone.utc)


def test_start_dt_accepts_fractional_seconds() -> None:
    activity = Activity.model_validate(
        _activity(1, "333", "2024-07-26T07:00:00.000Z", "2024-07-26T08:00:00.500Z")
    )
    assert activity.start_dt == datetime(2024, 7, 26, 7, 0, tzinfo=timezone.utc)
    assert activity.end_dt == datetime(2024, 7, 26, 8, 0, 0, 500000, tzinfo=timezone.utc)


def test_start_dt_treats_naive_timestamp_as_utc() -> None:
    activity = Activity.model_validate(
        _activity(1, "333", "2024-07-26T07:00:00", "2024-07-26T08:00:00")
    )
    assert activity.start_dt == datetime(2024, 7, 26, 7, 0, tzinfo=timezone.utc)
    assert activity.start_dt.utcoffset() == timedelta(0)


def test_start_dt_is_timezone_aware_for_lowercase_z() -> None:
    activity = Activity.model_validate(
        _activity(1, "333", "2024-07-26T07:00:00z", "2024-07-26T08:00:00z")
    )
    assert activity.start_dt == datetime(2024, 7, 26, 7, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Construction of nested models
# ---------------------------------------------------------------------------


def test_round_time_limit_cutoff_and_advancement_parse(comp: Competition) -> None:
    round_ = comp.events[0].rounds[0]
    assert isinstance(round_.time_limit, TimeLimit)
    assert round_.time_limit.centiseconds == 60000
    assert isinstance(round_.cutoff, Cutoff)
    assert round_.cutoff.number_of_attempts == 2
    assert round_.cutoff.attempt_result == 3000
    assert isinstance(round_.advancement_condition, AdvancementCondition)
    assert round_.advancement_condition.type == AdvancementType.PERCENT
    assert round_.advancement_condition.level == 75


def test_person_registration_parses_into_model(comp: Competition) -> None:
    registration = comp.persons[0].registration
    assert isinstance(registration, Registration)
    assert registration.status == RegistrationStatus.ACCEPTED


def test_result_model_parses_attempts() -> None:
    result = Result.model_validate(
        {"personId": 7, "best": 1000, "average": 1100, "attempts": [{"result": 1000}]}
    )
    assert isinstance(result.attempts[0], Attempt)
    assert result.ranking is None


def test_personal_best_parses_camel_case_rankings() -> None:
    best = PersonalBest.model_validate(
        {
            "eventId": "333",
            "best": 421,
            "worldRanking": 10,
            "continentalRanking": 3,
            "nationalRanking": 1,
            "type": "single",
        }
    )
    assert best.world_ranking == 10
    assert best.continental_ranking == 3
    assert best.national_ranking == 1
    assert best.type == ResultType.SINGLE


def test_mutable_defaults_are_not_shared_between_instances() -> None:
    first = Person(name="A", wca_user_id=1, country_iso2="GR", gender="f")
    second = Person(name="B", wca_user_id=2, country_iso2="GR", gender="f")
    first.roles.append(Role.DELEGATE)
    assert second.roles == []


def test_assignment_code_enum_value_round_trips() -> None:
    assignment = Assignment(activity_id=5, assignment_code=AssignmentCode.STAFF_RUNNER)
    assert assignment.to_wcif_dict()["assignmentCode"] == "staff-runner"


def test_gender_enum_value_round_trips() -> None:
    person = Person(name="A", wca_user_id=1, country_iso2="GR", gender=Gender.OTHER)
    assert person.to_wcif_dict()["gender"] == "o"


def test_result_attempt_values_are_kept(comp: Competition) -> None:
    payload = copy.deepcopy(_competition_payload())
    payload["events"][0]["rounds"][0]["results"] = [
        {"personId": 1, "ranking": 1, "best": -2, "average": -2, "attempts": [{"result": -2}]}
    ]
    dumped = Competition.model_validate(payload).to_wcif_dict()
    result = dumped["events"][0]["rounds"][0]["results"][0]
    assert result["ranking"] == 1
    assert result["attempts"] == [{"result": -2}]


# ---------------------------------------------------------------------------
# Competition helpers
# ---------------------------------------------------------------------------


def test_get_person_by_registrant_id(comp: Competition) -> None:
    person = comp.get_person(registrant_id=2)
    assert person is not None
    assert person.name == "Bob Judge"


def test_get_person_by_wca_id(comp: Competition) -> None:
    person = comp.get_person(wca_id="2010ABCD01")
    assert person is not None
    assert person.name == "Alice Competitor"


def test_get_person_by_wca_user_id(comp: Competition) -> None:
    person = comp.get_person(wca_user_id=103)
    assert person is not None
    assert person.name == "Carol FirstTimer"


def test_get_person_returns_none_when_missing(comp: Competition) -> None:
    assert comp.get_person(registrant_id=999) is None
    assert comp.get_person(wca_id="1999NOPE01") is None
    assert comp.get_person(wca_user_id=0) is None


def test_get_person_without_criteria_returns_none(comp: Competition) -> None:
    assert comp.get_person() is None


def test_get_person_requires_all_given_criteria(comp: Competition) -> None:
    assert comp.get_person(registrant_id=1, wca_id="2010ABCD01") is not None
    assert comp.get_person(registrant_id=1, wca_id="2012JUDG01") is None
    assert comp.get_person(registrant_id=1, wca_user_id=102) is None


def test_get_person_returns_first_match_on_duplicate_keys() -> None:
    payload = _competition_payload()
    duplicate = copy.deepcopy(payload["persons"][0])
    duplicate["name"] = "Duplicate"
    payload["persons"].append(duplicate)
    comp = Competition.model_validate(payload)
    person = comp.get_person(registrant_id=1)
    assert person is not None
    assert person.name == "Alice Competitor"


def test_get_accepted_competitors_all_events(comp: Competition) -> None:
    names = [person.name for person in comp.get_accepted_competitors()]
    assert names == ["Alice Competitor", "Carol FirstTimer"]


def test_get_accepted_competitors_filters_by_event(comp: Competition) -> None:
    names = [person.name for person in comp.get_accepted_competitors("333fm")]
    assert names == ["Alice Competitor"]


def test_get_accepted_competitors_empty_for_unregistered_event(comp: Competition) -> None:
    assert comp.get_accepted_competitors("444") == []


def test_get_accepted_competitors_excludes_pending_and_non_competing(comp: Competition) -> None:
    names = {person.name for person in comp.get_accepted_competitors()}
    assert "Eve Pending" not in names
    assert "Frank Spectator" not in names
    assert "Bob Judge" not in names
    assert "Dan Delegate" not in names


def test_get_accepted_competitors_excludes_deleted_and_unknown_status() -> None:
    payload = _competition_payload()
    payload["persons"][0]["registration"]["status"] = "deleted"
    payload["persons"][2]["registration"]["status"] = "withdrawn"
    comp = Competition.model_validate(payload)
    assert comp.get_accepted_competitors() == []


def test_get_first_timers(comp: Competition) -> None:
    names = [person.name for person in comp.get_first_timers()]
    assert names == ["Carol FirstTimer"]


def test_get_first_timers_excludes_unregistered_persons_without_wca_id() -> None:
    payload = _competition_payload()
    payload["persons"][2]["registration"] = None
    comp = Competition.model_validate(payload)
    assert comp.get_first_timers() == []


def test_get_staff_includes_roles_and_judge_assignments(comp: Competition) -> None:
    names = [person.name for person in comp.get_staff()]
    assert names == ["Bob Judge", "Dan Delegate"]


def test_get_staff_excludes_pure_competitors(comp: Competition) -> None:
    names = {person.name for person in comp.get_staff()}
    assert "Alice Competitor" not in names
    assert "Carol FirstTimer" not in names


def test_get_staff_includes_custom_non_competitor_assignment() -> None:
    payload = _competition_payload()
    payload["persons"][0]["assignments"] = [{"activityId": 1, "assignmentCode": "staff-foo"}]
    comp = Competition.model_validate(payload)
    assert comp.get_staff()[0].name == "Alice Competitor"


def test_get_event(comp: Competition) -> None:
    event = comp.get_event("333fm")
    assert event is not None
    assert event.id == "333fm"
    assert comp.get_event("nope") is None


def test_get_round(comp: Competition) -> None:
    round_ = comp.get_round("333-r2")
    assert round_ is not None
    assert round_.id == "333-r2"
    assert comp.get_round("333fm-r1") is not None
    assert comp.get_round("missing-r9") is None


def test_iter_activities_depth_first_with_children(comp: Competition) -> None:
    ids = [activity.id for _, _, activity in comp.iter_activities()]
    assert ids == [100, 101, 102, 200, 300, 400]


def test_iter_activities_without_children(comp: Competition) -> None:
    ids = [activity.id for _, _, activity in comp.iter_activities(include_children=False)]
    assert ids == [100, 200, 300, 400]


def test_iter_activities_yields_venue_and_room(comp: Competition) -> None:
    rows = {
        activity.id: (venue.name, room.name) for venue, room, activity in comp.iter_activities()
    }
    assert rows[101] == ("Athens Venue", "Main Hall")
    assert rows[300] == ("Athens Venue", "Side Room")
    assert rows[400] == ("New York Venue", "Hall NY")


def test_get_activity_finds_child(comp: Competition) -> None:
    found = comp.get_activity(102)
    assert found is not None
    venue, room, activity = found
    assert venue.name == "Athens Venue"
    assert room.name == "Main Hall"
    assert activity.activity_code == "333-r1-g2"


def test_get_activity_finds_top_level(comp: Competition) -> None:
    found = comp.get_activity(200)
    assert found is not None
    assert found[2].activity_code == "other-lunch"


def test_get_activity_missing_returns_none(comp: Competition) -> None:
    assert comp.get_activity(999) is None


def test_get_person_schedule_returns_local_times_sorted(comp: Competition) -> None:
    entries = comp.get_person_schedule(1)
    assert [entry.activity.id for entry in entries] == [300, 102]

    first, second = entries

    assert first.venue.timezone == "Europe/Athens"
    assert first.room.name == "Side Room"
    assert first.local_start.hour == 9
    assert first.local_start.minute == 0
    assert first.local_end.hour == 9
    assert first.local_end.minute == 30
    assert first.local_start.utcoffset() == timedelta(hours=3)

    assert second.room.name == "Main Hall"
    assert second.local_start.hour == 10
    assert second.local_start.minute == 30
    assert second.local_end.hour == 11
    assert second.local_end.minute == 0
    assert second.assignment.assignment_code == "competitor"


def test_get_person_schedule_converts_each_venue_to_its_own_timezone(comp: Competition) -> None:
    entries = comp.get_person_schedule(2)
    assert [entry.activity.id for entry in entries] == [101, 400]

    athens_entry, ny_entry = entries
    assert athens_entry.venue.timezone == "Europe/Athens"
    assert athens_entry.local_start.hour == 10
    assert athens_entry.assignment.station_number == 2

    assert ny_entry.venue.timezone == "America/New_York"
    assert ny_entry.local_start.hour == 9
    assert ny_entry.local_start.minute == 0
    assert ny_entry.local_end.hour == 10
    assert ny_entry.local_start.utcoffset() == timedelta(hours=-4)


def test_get_person_schedule_local_times_refer_to_same_instant_as_utc(comp: Competition) -> None:
    for entry in comp.get_person_schedule(2):
        assert entry.local_start == entry.activity.start_dt
        assert entry.local_end == entry.activity.end_dt


def test_get_person_schedule_is_sorted_chronologically() -> None:
    payload = _competition_payload()
    # Put the NY activity (13:00Z) before the Athens one (07:00Z) in the assignment list.
    payload["persons"][1]["assignments"] = [
        {"activityId": 400, "assignmentCode": "judge"},
        {"activityId": 101, "assignmentCode": "judge"},
    ]
    comp = Competition.model_validate(payload)
    starts = [entry.local_start for entry in comp.get_person_schedule(2)]
    assert starts == sorted(starts)
    assert [entry.activity.id for entry in comp.get_person_schedule(2)] == [101, 400]


def test_get_person_schedule_skips_unknown_activities(comp: Competition) -> None:
    ids = [entry.activity.id for entry in comp.get_person_schedule(1)]
    assert 999 not in ids


def test_get_person_schedule_returns_empty_for_unknown_registrant(comp: Competition) -> None:
    assert comp.get_person_schedule(999) == []


def test_get_person_schedule_returns_empty_for_person_without_assignments(
    comp: Competition,
) -> None:
    assert comp.get_person_schedule(3) == []


def test_get_person_schedule_entry_fields_are_the_schedule_objects(comp: Competition) -> None:
    entry = comp.get_person_schedule(2)[0]
    found = comp.get_activity(101)
    assert found is not None
    assert entry.activity == found[2]
    assert entry.room == found[1]
    assert entry.venue == found[0]
    assert isinstance(entry.venue, Venue)
    assert entry.local_start.tzinfo is not None


def test_helpers_are_stateless(comp: Competition) -> None:
    before = comp.to_wcif_dict()
    comp.get_accepted_competitors()
    comp.get_first_timers()
    comp.get_staff()
    list(comp.iter_activities())
    comp.get_person_schedule(1)
    assert comp.to_wcif_dict() == before


def test_competition_with_empty_schedule_has_no_activities() -> None:
    comp = Competition.model_validate(
        {
            "id": "E",
            "name": "E",
            "shortName": "E",
            "schedule": {"startDate": "2024-01-01", "numberOfDays": 1},
        }
    )
    assert list(comp.iter_activities()) == []
    assert comp.get_activity(1) is None
    assert comp.get_person_schedule(1) == []
