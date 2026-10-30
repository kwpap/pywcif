"""Activity code parsing and rendering helpers for WCIF schedules.

A competition activity code has the grammar ``<eventId>(-r<N>)?(-g<N>)?(-a<N>)?``. The optional
round, group and attempt tokens must appear in that order, and each number is a positive integer
written without leading zeros, e.g. ``333-r1-g2-a1``. Non-competition activities use the form
``other-<name>`` (e.g. ``other-lunch``) and carry no numbers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_OTHER_PREFIX = "other-"
_EVENT_ID_RE = re.compile(r"[a-z0-9]+")
_OTHER_CODE_RE = re.compile(r"other-[a-z0-9]+")
_NUMBER_RE = re.compile(r"[1-9][0-9]*")
# Token prefixes for round, group and attempt, in the only order they may appear.
_TOKEN_PREFIXES = ("r", "g", "a")


@dataclass(frozen=True)
class ActivityCode:
    """A parsed WCIF activity code.

    Attributes:
        event_id: Event identifier such as ``"333"`` or ``"333fm"``. For non-competition
            activities this is the whole code, such as ``"other-lunch"``.
        round_number: Round number, or ``None`` if the code does not name one.
        group_number: Group number, or ``None`` if the code does not name one.
        attempt_number: Attempt number, or ``None`` if the code does not name one.

    Instances are immutable and hashable. Use :meth:`parse` to build one from a string;
    direct construction is validated the same way.
    """

    event_id: str
    round_number: int | None = None
    group_number: int | None = None
    attempt_number: int | None = None

    def __post_init__(self) -> None:
        numbers = (self.round_number, self.group_number, self.attempt_number)
        if self.is_official_event:
            if not _EVENT_ID_RE.fullmatch(self.event_id):
                raise ValueError(f"invalid event id {self.event_id!r}")
            for value in numbers:
                if value is not None and value < 1:
                    raise ValueError(f"activity code numbers must be positive, got {value}")
        else:
            if not _OTHER_CODE_RE.fullmatch(self.event_id):
                raise ValueError(f"invalid non-competition activity code {self.event_id!r}")
            if any(value is not None for value in numbers):
                raise ValueError(
                    f"non-competition activity code {self.event_id!r} cannot have "
                    "round, group or attempt numbers"
                )

    @classmethod
    def parse(cls, code: str) -> ActivityCode:
        """Parse an activity code string.

        Args:
            code: A code such as ``"333-r1-g2-a1"``, ``"333"`` or ``"other-lunch"``.

        Returns:
            The parsed activity code.

        Raises:
            ValueError: If the code is empty, has an unknown, duplicated or out-of-order token,
                has a non-positive or non-canonical number, or has an invalid event id.
        """
        if not code:
            raise ValueError("activity code must not be empty")
        if code.startswith(_OTHER_PREFIX):
            return cls(event_id=code)

        event_id, *tokens = code.split("-")
        numbers: dict[str, int] = {}
        last_position = -1
        for token in tokens:
            if not token:
                raise ValueError(f"empty token in activity code {code!r}")
            prefix, digits = token[:1], token[1:]
            if prefix not in _TOKEN_PREFIXES:
                raise ValueError(f"unknown token {token!r} in activity code {code!r}")
            if prefix in numbers:
                raise ValueError(f"duplicate {prefix!r} token in activity code {code!r}")
            position = _TOKEN_PREFIXES.index(prefix)
            if position < last_position:
                raise ValueError(f"token {token!r} is out of order in activity code {code!r}")
            if not _NUMBER_RE.fullmatch(digits):
                raise ValueError(f"token {token!r} must end in a positive integer")
            numbers[prefix] = int(digits)
            last_position = position

        return cls(
            event_id=event_id,
            round_number=numbers.get("r"),
            group_number=numbers.get("g"),
            attempt_number=numbers.get("a"),
        )

    def __str__(self) -> str:
        """Render the canonical code string, the inverse of :meth:`parse`."""
        if not self.is_official_event:
            return self.event_id
        parts = [self.event_id]
        for prefix, value in (
            ("r", self.round_number),
            ("g", self.group_number),
            ("a", self.attempt_number),
        ):
            if value is not None:
                parts.append(f"{prefix}{value}")
        return "-".join(parts)

    @property
    def is_official_event(self) -> bool:
        """``False`` for non-competition codes (those starting with ``other-``), else ``True``."""
        return not self.event_id.startswith(_OTHER_PREFIX)

    def is_parent_of(self, other: ActivityCode) -> bool:
        """Return whether this code is a strictly broader match for ``other``.

        That is true when both codes are for the same competition event, this code is not equal
        to ``other``, and every round, group or attempt number set on this code equals the
        matching number on ``other``. For example ``333`` is a parent of ``333-r1``, and
        ``333-r1`` is a parent of ``333-r1-g2``. Non-competition codes are never parents.
        """
        if not self.is_official_event or not other.is_official_event:
            return False
        if self == other or self.event_id != other.event_id:
            return False
        pairs = (
            (self.round_number, other.round_number),
            (self.group_number, other.group_number),
            (self.attempt_number, other.attempt_number),
        )
        return all(mine is None or mine == theirs for mine, theirs in pairs)
