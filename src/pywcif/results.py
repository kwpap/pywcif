"""Result parsing and formatting interfaces for WCIF data.

WCIF stores attempt and round results as integers:

* ``-1`` means DNF (did not finish), ``-2`` means DNS (did not start), and ``0`` means
  skipped / no result.
* Times are centiseconds (``1045`` is ``10.45`` seconds).
* Multi-blind results are packed into a single integer, in either the new-style
  ``0DDTTTTTMM`` layout or the legacy ``1SSAATTTTT`` layout used by ``333mbo``.
* Fewest-moves (``333fm``) single results are move counts; averages are centimoves.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

DNF: Final = -1
"""WCIF value for "did not finish"."""

DNS: Final = -2
"""WCIF value for "did not start"."""

SKIPPED: Final = 0
"""WCIF value for a skipped attempt or an empty result."""

_UNKNOWN_TIME: Final = 99999
"""Packed time value meaning "time unknown" in multi-blind results."""

_OLD_STYLE_OFFSET: Final = 10**9
"""Leading digit of legacy (``333mbo``) multi-blind results."""

_MULTI_BLIND_EVENTS: Final = ("333mbf", "333mbo")
_FMC_EVENT: Final = "333fm"

_CLOCK_RE: Final = re.compile(
    r"(?:(?:(?P<hours>[0-9]+):)?(?P<minutes>[0-9]+):)?"
    r"(?P<seconds>[0-9]+)(?:\.(?P<fraction>[0-9]{1,2}))?"
)


def is_dnf(value: int) -> bool:
    """Return True if ``value`` is the WCIF DNF marker (``-1``)."""
    return value == DNF


def is_dns(value: int) -> bool:
    """Return True if ``value`` is the WCIF DNS marker (``-2``)."""
    return value == DNS


def is_skipped(value: int) -> bool:
    """Return True if ``value`` is the WCIF skipped marker (``0``)."""
    return value == SKIPPED


def centiseconds_to_str(cs: int) -> str:
    """Format a centisecond duration the way WCA result strings are shown.

    Seconds are always shown; minutes and hours are added only when non-zero.

    Examples:
        ``1045`` -> ``"10.45"``, ``6543`` -> ``"1:05.43"``, ``360000`` -> ``"1:00:00.00"``.

    Args:
        cs: Duration in centiseconds. Must be non-negative.

    Returns:
        The formatted time string.

    Raises:
        ValueError: If ``cs`` is negative.
    """
    if cs < 0:
        raise ValueError(f"Cannot format negative duration: {cs}")
    centis = cs % 100
    total_seconds = cs // 100
    seconds = total_seconds % 60
    total_minutes = total_seconds // 60
    minutes = total_minutes % 60
    hours = total_minutes // 60
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}.{centis:02d}"
    if total_minutes:
        return f"{minutes}:{seconds:02d}.{centis:02d}"
    return f"{seconds}.{centis:02d}"


def str_to_centiseconds(s: str) -> int:
    """Parse a WCA result string into centiseconds. Inverse of :func:`centiseconds_to_str`.

    Accepts ``S``, ``S.f``, ``S.ff``, ``M:SS``, ``M:SS.ff`` and ``H:MM:SS.ff`` (with optional
    fractional digits; a single fractional digit means tenths). Whitespace is ignored and
    ``DNF`` / ``DNS`` are accepted case-insensitively.

    Args:
        s: The string to parse.

    Returns:
        The duration in centiseconds, or ``-1`` / ``-2`` for DNF / DNS.

    Raises:
        ValueError: If ``s`` is not a valid time, including when minutes or hours are present
            and the seconds (or minutes) field is 60 or more.
    """
    text = s.strip()
    upper = text.upper()
    if upper == "DNF":
        return DNF
    if upper == "DNS":
        return DNS
    match = _CLOCK_RE.fullmatch(text)
    if match is None:
        raise ValueError(f"Invalid result time: {s!r}")
    hours_part = match.group("hours")
    minutes_part = match.group("minutes")
    seconds_part = match.group("seconds")
    fraction_part = match.group("fraction")

    hours = int(hours_part) if hours_part is not None else 0
    minutes = int(minutes_part) if minutes_part is not None else 0
    seconds = int(seconds_part)
    if minutes_part is not None and seconds >= 60:
        raise ValueError(f"Seconds must be below 60 when minutes are given: {s!r}")
    if hours_part is not None and minutes >= 60:
        raise ValueError(f"Minutes must be below 60 when hours are given: {s!r}")
    centis = int(fraction_part.ljust(2, "0")) if fraction_part is not None else 0
    return ((hours * 60 + minutes) * 60 + seconds) * 100 + centis


@dataclass(frozen=True)
class MultiBlindResult:
    """A decoded multi-blind (MBLD) result.

    Attributes:
        solved: Number of cubes solved.
        attempted: Number of cubes attempted.
        time_seconds: Elapsed time in whole seconds, or ``None`` when the time is unknown.
        is_old_style: True for the legacy ``333mbo`` packing, False for ``333mbf``.
    """

    solved: int
    attempted: int
    time_seconds: int | None
    is_old_style: bool = False

    def __post_init__(self) -> None:
        """Reject values that cannot describe a real multi-blind result."""
        if self.solved < 0 or self.attempted < 0:
            raise ValueError("solved and attempted must be non-negative")
        if self.time_seconds is not None and not 0 <= self.time_seconds < _UNKNOWN_TIME:
            raise ValueError(f"time_seconds must be in [0, {_UNKNOWN_TIME}): {self.time_seconds}")

    @classmethod
    def from_wcif_int(cls, value: int, *, event_id: str | None = None) -> MultiBlindResult:
        """Decode a packed multi-blind integer.

        The new-style layout is ``0DDTTTTTMM``: ``MM`` is the number of misses, ``TTTTT`` the
        time in seconds (``99999`` = unknown), and ``DD = 99 - (solved - missed)``.

        The legacy layout is ``1SSAATTTTT``: ``SS = 99 - solved``, ``AA`` is attempted, and
        ``TTTTT`` the time in seconds.

        Old style is chosen when ``event_id`` is ``"333mbo"`` or the value is at least
        ``10**9``.

        Args:
            value: The packed WCIF integer. Must be positive.
            event_id: Optional event id, used to select the legacy layout.

        Returns:
            The decoded result.

        Raises:
            ValueError: If ``value`` is not positive. DNF, DNS and skipped values are not
                multi-blind results.
        """
        if value <= 0:
            raise ValueError(f"Not a multi-blind result: {value}")
        if event_id == "333mbo" or value >= _OLD_STYLE_OFFSET:
            time_raw = value % 100000
            attempted = (value // 100000) % 100
            solved = 99 - ((value // 10_000_000) % 100)
            return cls(
                solved=solved,
                attempted=attempted,
                time_seconds=None if time_raw == _UNKNOWN_TIME else time_raw,
                is_old_style=True,
            )
        missed = value % 100
        time_raw = (value // 100) % 100000
        difference = 99 - (value // 10_000_000)
        solved = difference + missed
        return cls(
            solved=solved,
            attempted=solved + missed,
            time_seconds=None if time_raw == _UNKNOWN_TIME else time_raw,
            is_old_style=False,
        )

    def to_wcif_int(self) -> int:
        """Pack this result into the WCIF integer. Exact inverse of :meth:`from_wcif_int`.

        Unknown time (``None``) is encoded as ``99999``.

        Returns:
            The packed integer, in the layout selected by ``is_old_style``.

        Raises:
            ValueError: If the counts cannot be represented in the packed layout (for example
                more misses than solved cubes in new style, or a count above 99).
        """
        time_value = _UNKNOWN_TIME if self.time_seconds is None else self.time_seconds
        if self.is_old_style:
            if not (0 <= self.solved <= 99 and 0 <= self.attempted <= 99):
                raise ValueError("Old-style multi-blind counts must be in [0, 99]")
            return (
                _OLD_STYLE_OFFSET + (99 - self.solved) * 10**7 + self.attempted * 10**5 + time_value
            )
        missed = self.attempted - self.solved
        difference = self.solved - missed
        if not (0 <= difference <= 99 and 0 <= missed <= 99):
            raise ValueError(
                f"Cannot encode multi-blind result solved={self.solved} attempted={self.attempted}"
            )
        return (99 - difference) * 10**7 + time_value * 100 + missed

    @property
    def missed(self) -> int:
        """Number of cubes attempted but not solved."""
        return self.attempted - self.solved

    @property
    def points(self) -> int:
        """Score as used by WCA: ``solved - missed``."""
        return self.solved - (self.attempted - self.solved)

    @property
    def formatted(self) -> str:
        """Human-readable form such as ``"12/13 54:12"``.

        The clock is ``M:SS`` with unpadded minutes. An unknown time shows as ``"??:??"``,
        giving e.g. ``"12/13 ??:??"``.
        """
        if self.time_seconds is None:
            clock = "??:??"
        else:
            minutes, seconds = divmod(self.time_seconds, 60)
            clock = f"{minutes}:{seconds:02d}"
        return f"{self.solved}/{self.attempted} {clock}"


def format_result(result: int, event_id: str, *, is_average: bool = False) -> str:
    """Format a raw WCIF result integer for display.

    Args:
        result: The raw WCIF value (attempt result, best, or average).
        event_id: The WCIF event id, e.g. ``"333"``, ``"333fm"`` or ``"333mbf"``.
        is_average: True when ``result`` is an average rather than a single. Only affects
            ``333fm``, where averages are centimoves (``2833`` -> ``"28.33"``).

    Returns:
        ``"DNF"``, ``"DNS"``, ``""`` for skipped, the move count or centimove average for
        ``333fm``, the multi-blind string for ``333mbf`` / ``333mbo``, or a clock time for
        every other event.

    Raises:
        ValueError: If ``result`` is negative and is not DNF or DNS.
    """
    if is_dnf(result):
        return "DNF"
    if is_dns(result):
        return "DNS"
    if is_skipped(result):
        return ""
    if result < 0:
        raise ValueError(f"Invalid result value: {result}")
    if event_id == _FMC_EVENT:
        if is_average:
            return f"{result // 100}.{result % 100:02d}"
        return str(result)
    if event_id in _MULTI_BLIND_EVENTS:
        return MultiBlindResult.from_wcif_int(result, event_id=event_id).formatted
    return centiseconds_to_str(result)
