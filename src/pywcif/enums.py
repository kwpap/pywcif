"""String enums for WCIF v1.2 vocabularies.

Every enum is a ``str`` subclass, so members compare equal to their raw WCIF
values. Model fields are typed ``EnumType | str`` so unknown values never fail
validation; these enums exist for autocomplete and documentation.
"""

from __future__ import annotations

from enum import Enum


class _StrEnum(str, Enum):
    """Python 3.10-compatible string enum whose ``str()`` is the raw value."""

    def __str__(self) -> str:
        return str(self.value)


class EventId(_StrEnum):
    """WCA event identifiers, including retired events."""

    E333 = "333"
    E222 = "222"
    E444 = "444"
    E555 = "555"
    E666 = "666"
    E777 = "777"
    E333BF = "333bf"
    E333FM = "333fm"
    E333OH = "333oh"
    CLOCK = "clock"
    MINX = "minx"
    PYRAM = "pyram"
    SKEWB = "skewb"
    SQ1 = "sq1"
    E444BF = "444bf"
    E555BF = "555bf"
    E333MBF = "333mbf"
    # Retired events.
    E333FT = "333ft"
    MAGIC = "magic"
    MMAGIC = "mmagic"
    E333MBO = "333mbo"


class RoundFormat(_StrEnum):
    """Round formats: number of attempts, average, or mean."""

    ONE = "1"
    TWO = "2"
    THREE = "3"
    AVERAGE = "a"
    MEAN = "m"


class AdvancementType(_StrEnum):
    """How advancement to the next round is determined."""

    RANKING = "ranking"
    PERCENT = "percent"
    ATTEMPT_RESULT = "attemptResult"


class AssignmentCode(_StrEnum):
    """Activity assignment codes for competitors and staff."""

    COMPETITOR = "competitor"
    STAFF_JUDGE = "staff-judge"
    STAFF_SCRAMBLER = "staff-scrambler"
    STAFF_RUNNER = "staff-runner"
    STAFF_DATAENTRY = "staff-dataentry"
    STAFF_ANNOUNCER = "staff-announcer"
    JUDGE = "judge"
    SCRAMBLER = "scrambler"
    RUNNER = "runner"
    DATAENTRY = "dataentry"
    ANNOUNCER = "announcer"


class RegistrationStatus(_StrEnum):
    """Registration lifecycle states."""

    ACCEPTED = "accepted"
    PENDING = "pending"
    DELETED = "deleted"
    WAITING_LIST = "waiting_list"


class QualificationType(_StrEnum):
    """How an event's qualification is evaluated."""

    ATTEMPT_RESULT = "attemptResult"
    RANKING = "ranking"
    ANY_RESULT = "anyResult"


class ResultType(_StrEnum):
    """Whether a result is a single or an average."""

    SINGLE = "single"
    AVERAGE = "average"


class Role(_StrEnum):
    """Competition roles attached to a person."""

    DELEGATE = "delegate"
    TRAINEE_DELEGATE = "trainee-delegate"
    ORGANIZER = "organizer"


class Gender(_StrEnum):
    """Gender codes used by WCIF."""

    M = "m"
    F = "f"
    OTHER = "o"


__all__ = [
    "AdvancementType",
    "AssignmentCode",
    "EventId",
    "Gender",
    "QualificationType",
    "RegistrationStatus",
    "ResultType",
    "Role",
    "RoundFormat",
]
