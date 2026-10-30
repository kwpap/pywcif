"""Core Pydantic models for WCIF v1.2 documents.

Python attributes are snake_case; the JSON wire format is camelCase. Models
accept either spelling. Unknown keys are kept (``extra="allow"``) so documents
survive a load/dump round-trip.

Serialization rules:

* *Required nullable* fields (for example ``wcaId`` or ``cutoff``) are always
  emitted, as ``null`` when empty.
* Fields listed in ``_OPTIONAL_OMITTABLE_FIELDS`` are omitted when they are
  ``None`` and were not set explicitly, so ``"email": null`` in the input is
  kept but a missing ``email`` stays missing.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, ClassVar
from zoneinfo import ZoneInfo

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    model_serializer,
)
from pydantic.alias_generators import to_camel

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

__all__ = [
    "Activity",
    "AdvancementCondition",
    "AdvancementType",
    "Assignment",
    "AssignmentCode",
    "Attempt",
    "Avatar",
    "Competition",
    "Cutoff",
    "Event",
    "EventId",
    "Extension",
    "Gender",
    "Person",
    "PersonScheduleEntry",
    "PersonalBest",
    "Qualification",
    "QualificationType",
    "Registration",
    "RegistrationStatus",
    "Result",
    "ResultType",
    "Role",
    "Room",
    "Round",
    "RoundFormat",
    "Schedule",
    "TimeLimit",
    "Venue",
    "WCIFModel",
]


class WCIFModel(BaseModel):
    """Base class for all WCIF models (camelCase aliases, unknown keys kept)."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="allow",
    )

    # Fields omitted from the output when they are None and were not set explicitly.
    _OPTIONAL_OMITTABLE_FIELDS: ClassVar[frozenset[str]] = frozenset()

    @model_serializer(mode="wrap")
    def _serialize_wcif(
        self, handler: SerializerFunctionWrapHandler, info: SerializationInfo
    ) -> Any:
        data = handler(self)
        if isinstance(data, dict):
            for name in self._OPTIONAL_OMITTABLE_FIELDS:
                if getattr(self, name, None) is None and name not in self.model_fields_set:
                    field = type(self).model_fields[name]
                    key = (
                        (field.serialization_alias or field.alias or name)
                        if info.by_alias
                        else name
                    )
                    data.pop(key, None)
        return data

    def to_wcif_dict(self) -> dict[str, Any]:
        """Return a plain JSON-compatible dict using WCIF (camelCase) keys."""
        return self.model_dump(mode="json", by_alias=True)

    def to_wcif_json(self, indent: int | None = None) -> str:
        """Return the WCIF JSON document as a string."""
        return self.model_dump_json(by_alias=True, indent=indent)


class Extension(WCIFModel):
    """A third-party extension block (``extensions`` entries)."""

    id: str
    spec_url: str
    data: dict[str, Any]


class Avatar(WCIFModel):
    """Profile picture URLs."""

    url: str
    thumb_url: str


class Registration(WCIFModel):
    """A person's registration for the competition."""

    _OPTIONAL_OMITTABLE_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {"guests", "comments", "administrative_notes"}
    )

    wca_registration_id: int
    event_ids: list[EventId | str]
    status: RegistrationStatus | str
    is_competing: bool = True
    guests: int | None = None
    comments: str | None = None
    administrative_notes: str | None = None


class Assignment(WCIFModel):
    """A person's assignment to an activity."""

    activity_id: int
    assignment_code: AssignmentCode | str
    station_number: int | None = None


class PersonalBest(WCIFModel):
    """A personal best record for one event."""

    event_id: EventId | str
    best: int
    world_ranking: int
    continental_ranking: int
    national_ranking: int
    type: ResultType | str


class Person(WCIFModel):
    """A competitor or staff member."""

    _OPTIONAL_OMITTABLE_FIELDS: ClassVar[frozenset[str]] = frozenset({"birthdate", "email"})

    registrant_id: int | None = None
    name: str
    wca_user_id: int
    wca_id: str | None = None
    country_iso2: str
    gender: Gender | str
    avatar: Avatar | None = None
    roles: list[Role | str] = Field(default_factory=list)
    registration: Registration | None = None
    assignments: list[Assignment] = Field(default_factory=list)
    personal_bests: list[PersonalBest] = Field(default_factory=list)
    extensions: list[Extension] = Field(default_factory=list)
    birthdate: str | None = None
    email: str | None = None


class Attempt(WCIFModel):
    """One attempt within a result. Negative values are DNF/DNS/skipped codes."""

    _OPTIONAL_OMITTABLE_FIELDS: ClassVar[frozenset[str]] = frozenset({"reconstruction"})

    result: int
    reconstruction: str | None = None


class Result(WCIFModel):
    """A person's result in one round."""

    person_id: int
    ranking: int | None = None
    attempts: list[Attempt] = Field(default_factory=list)
    best: int
    average: int


class TimeLimit(WCIFModel):
    """Time limit for a round, optionally cumulative across earlier rounds."""

    centiseconds: int
    cumulative_round_ids: list[str] = Field(default_factory=list)


class Cutoff(WCIFModel):
    """Cutoff: the attempt count and the result needed to continue past attempt N."""

    number_of_attempts: int
    attempt_result: int


class AdvancementCondition(WCIFModel):
    """How many competitors advance from a round."""

    type: AdvancementType | str
    level: int


class Qualification(WCIFModel):
    """Qualification standard for an event.

    The date is read from ``whenDate`` (or the legacy ``when``) and written as ``whenDate``.
    """

    _OPTIONAL_OMITTABLE_FIELDS: ClassVar[frozenset[str]] = frozenset({"level"})

    when_date: str = Field(
        validation_alias=AliasChoices("whenDate", "when", "when_date"),
        serialization_alias="whenDate",
    )
    type: QualificationType | str
    result_type: ResultType | str
    level: int | None = None


class Round(WCIFModel):
    """A round of an event."""

    _OPTIONAL_OMITTABLE_FIELDS: ClassVar[frozenset[str]] = frozenset({"scramble_sets"})

    id: str
    format: RoundFormat | str
    time_limit: TimeLimit | None = None
    cutoff: Cutoff | None = None
    advancement_condition: AdvancementCondition | None = None
    results: list[Result] = Field(default_factory=list)
    scramble_set_count: int = 1
    scramble_sets: list[Any] | None = None
    extensions: list[Extension] = Field(default_factory=list)


class Event(WCIFModel):
    """An event with its rounds and qualification."""

    _OPTIONAL_OMITTABLE_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {"competitor_limit", "qualification"}
    )

    id: EventId | str
    rounds: list[Round] = Field(default_factory=list)
    competitor_limit: int | None = None
    qualification: Qualification | None = None
    extensions: list[Extension] = Field(default_factory=list)


def _parse_iso_datetime(value: str) -> datetime:
    """Parse an ISO 8601 timestamp into an aware UTC datetime.

    Python 3.10 ``fromisoformat`` rejects a trailing ``Z``, so it is replaced first.
    Naive timestamps are treated as UTC.
    """
    text = value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class Activity(WCIFModel):
    """A scheduled activity. Activities may nest through ``child_activities``.

    ``scramble_set_id`` is nullable in the WCIF spec, but the live WCA website omits the key
    entirely, so it is only emitted when the input had it (or it was set explicitly).
    """

    _OPTIONAL_OMITTABLE_FIELDS: ClassVar[frozenset[str]] = frozenset({"scramble_set_id"})

    id: int
    name: str
    activity_code: str
    start_time: str
    end_time: str
    child_activities: list[Activity] = Field(default_factory=list)
    scramble_set_id: int | None = None
    extensions: list[Extension] = Field(default_factory=list)

    @property
    def parsed_code(self) -> ActivityCode:
        """The ``activity_code`` parsed into an ``ActivityCode``."""
        return ActivityCode.parse(self.activity_code)

    @property
    def start_dt(self) -> datetime:
        """The start time as an aware UTC datetime."""
        return _parse_iso_datetime(self.start_time)

    @property
    def end_dt(self) -> datetime:
        """The end time as an aware UTC datetime."""
        return _parse_iso_datetime(self.end_time)


class Room(WCIFModel):
    """A room within a venue, holding activities."""

    id: int
    name: str
    color: str
    activities: list[Activity] = Field(default_factory=list)
    extensions: list[Extension] = Field(default_factory=list)


class Venue(WCIFModel):
    """A venue with an IANA timezone and rooms."""

    id: int
    name: str
    latitude_microdegrees: int
    longitude_microdegrees: int
    country_iso2: str
    timezone: str
    rooms: list[Room] = Field(default_factory=list)
    extensions: list[Extension] = Field(default_factory=list)


class Schedule(WCIFModel):
    """The competition schedule."""

    start_date: str
    number_of_days: int
    venues: list[Venue] = Field(default_factory=list)


@dataclass(frozen=True)
class PersonScheduleEntry:
    """One assignment of a person, joined with its activity, room and venue.

    ``local_start`` and ``local_end`` are in the venue's timezone.
    """

    assignment: Assignment
    activity: Activity
    room: Room
    venue: Venue
    local_start: datetime
    local_end: datetime


def _walk_activities(
    venue: Venue, room: Room, activities: list[Activity], include_children: bool
) -> Iterator[tuple[Venue, Room, Activity]]:
    """Yield activities depth-first, each parent before its children."""
    for activity in activities:
        yield venue, room, activity
        if include_children:
            yield from _walk_activities(venue, room, activity.child_activities, True)


class Competition(WCIFModel):
    """The root WCIF document."""

    _OPTIONAL_OMITTABLE_FIELDS: ClassVar[frozenset[str]] = frozenset({"series"})

    format_version: str = "1.0"
    id: str
    name: str
    short_name: str
    persons: list[Person] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    schedule: Schedule
    competitor_limit: int | None = None
    extensions: list[Extension] = Field(default_factory=list)
    series: dict[str, Any] | None = None

    def get_person(
        self,
        *,
        registrant_id: int | None = None,
        wca_id: str | None = None,
        wca_user_id: int | None = None,
    ) -> Person | None:
        """Return the first person matching every given criterion, or None.

        Returns None when no criterion is given.
        """
        if registrant_id is None and wca_id is None and wca_user_id is None:
            return None
        for person in self.persons:
            if registrant_id is not None and person.registrant_id != registrant_id:
                continue
            if wca_id is not None and person.wca_id != wca_id:
                continue
            if wca_user_id is not None and person.wca_user_id != wca_user_id:
                continue
            return person
        return None

    def get_accepted_competitors(self, event_id: str | None = None) -> list[Person]:
        """Return accepted, competing persons, optionally only those registered for an event."""
        result: list[Person] = []
        for person in self.persons:
            registration = person.registration
            if registration is None:
                continue
            if registration.status != RegistrationStatus.ACCEPTED or not registration.is_competing:
                continue
            if event_id is not None and event_id not in registration.event_ids:
                continue
            result.append(person)
        return result

    def get_first_timers(self) -> list[Person]:
        """Return accepted competitors who have no WCA ID."""
        return [person for person in self.get_accepted_competitors() if person.wca_id is None]

    def get_staff(self) -> list[Person]:
        """Return persons with a role or with any non-competitor assignment."""
        return [
            person
            for person in self.persons
            if person.roles
            or any(
                assignment.assignment_code != AssignmentCode.COMPETITOR
                for assignment in person.assignments
            )
        ]

    def get_event(self, event_id: str) -> Event | None:
        """Return the event with the given id, or None."""
        for event in self.events:
            if event.id == event_id:
                return event
        return None

    def get_round(self, round_id: str) -> Round | None:
        """Return the round with the given id from any event, or None."""
        for event in self.events:
            for round_ in event.rounds:
                if round_.id == round_id:
                    return round_
        return None

    def iter_activities(
        self, *, include_children: bool = True
    ) -> Iterator[tuple[Venue, Room, Activity]]:
        """Yield ``(venue, room, activity)`` for every activity, depth-first.

        Parents are yielded before their children. Set ``include_children=False`` to
        yield only top-level activities.
        """
        for venue in self.schedule.venues:
            for room in venue.rooms:
                yield from _walk_activities(venue, room, room.activities, include_children)

    def get_activity(self, activity_id: int) -> tuple[Venue, Room, Activity] | None:
        """Return ``(venue, room, activity)`` for an activity id, searching children too."""
        for venue, room, activity in self.iter_activities():
            if activity.id == activity_id:
                return venue, room, activity
        return None

    def get_person_schedule(self, registrant_id: int) -> list[PersonScheduleEntry]:
        """Return a person's scheduled assignments in local venue time, sorted by start.

        Assignments whose activity is not in the schedule are skipped. Returns an empty
        list when no person has the given registrant id.
        """
        person = self.get_person(registrant_id=registrant_id)
        if person is None:
            return []
        located: dict[int, tuple[Venue, Room, Activity]] = {}
        for venue, room, activity in self.iter_activities():
            located.setdefault(activity.id, (venue, room, activity))

        entries: list[PersonScheduleEntry] = []
        for assignment in person.assignments:
            found = located.get(assignment.activity_id)
            if found is None:
                continue
            venue, room, activity = found
            zone = ZoneInfo(venue.timezone)
            entries.append(
                PersonScheduleEntry(
                    assignment=assignment,
                    activity=activity,
                    room=room,
                    venue=venue,
                    local_start=activity.start_dt.astimezone(zone),
                    local_end=activity.end_dt.astimezone(zone),
                )
            )
        entries.sort(key=lambda entry: entry.local_start)
        return entries
