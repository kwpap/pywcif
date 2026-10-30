"""Tests for WCIF result encoding, decoding and formatting."""

from __future__ import annotations

import dataclasses

import pytest

from pywcif.results import (
    DNF,
    DNS,
    SKIPPED,
    MultiBlindResult,
    centiseconds_to_str,
    format_result,
    is_dnf,
    is_dns,
    is_skipped,
    str_to_centiseconds,
)

# --- constants and predicates -------------------------------------------------


def test_sentinel_constants() -> None:
    """DNF, DNS and SKIPPED use the WCIF sentinel values."""
    assert DNF == -1
    assert DNS == -2
    assert SKIPPED == 0


@pytest.mark.parametrize(
    ("value", "expected"),
    [(-1, True), (-2, False), (0, False), (1, False), (1045, False)],
)
def test_is_dnf(value: int, expected: bool) -> None:
    """is_dnf is True only for -1."""
    assert is_dnf(value) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(-2, True), (-1, False), (0, False), (1, False), (1045, False)],
)
def test_is_dns(value: int, expected: bool) -> None:
    """is_dns is True only for -2."""
    assert is_dns(value) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0, True), (-1, False), (-2, False), (1, False), (1045, False)],
)
def test_is_skipped(value: int, expected: bool) -> None:
    """is_skipped is True only for 0."""
    assert is_skipped(value) is expected


# --- centiseconds_to_str ------------------------------------------------------


@pytest.mark.parametrize(
    ("cs", "expected"),
    [
        # sub-minute
        (0, "0.00"),
        (1, "0.01"),
        (5, "0.05"),
        (100, "1.00"),
        (1045, "10.45"),
        (5999, "59.99"),
        # exactly one minute and just around it
        (6000, "1:00.00"),
        (6001, "1:00.01"),
        # multi-minute
        (6543, "1:05.43"),
        (59999, "9:59.99"),
        (60000, "10:00.00"),
        (61234, "10:12.34"),
        # more than ten minutes, still under an hour
        (359999, "59:59.99"),
        # exactly one hour and above
        (360000, "1:00:00.00"),
        (372345, "1:02:03.45"),
        (3_600_000, "10:00:00.00"),
        (36_000_000, "100:00:00.00"),
    ],
)
def test_centiseconds_to_str(cs: int, expected: str) -> None:
    """Durations format with seconds always, minutes and hours only when non-zero."""
    assert centiseconds_to_str(cs) == expected


@pytest.mark.parametrize("cs", [-1, -100, -360001])
def test_centiseconds_to_str_rejects_negative(cs: int) -> None:
    """Negative durations raise ValueError."""
    with pytest.raises(ValueError, match="negative"):
        centiseconds_to_str(cs)


# --- str_to_centiseconds ------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("0", 0),
        ("0.00", 0),
        ("0.05", 5),
        ("0.5", 50),
        ("10", 1000),
        ("10.4", 1040),
        ("10.04", 1004),
        ("10.45", 1045),
        ("1:00", 6000),
        ("1:00.00", 6000),
        ("1:05.43", 6543),
        ("00:10.45", 1045),
        ("10:00.00", 60000),
        ("59:59.99", 359999),
        ("1:00:00", 360000),
        ("1:00:00.00", 360000),
        ("1:02:03.45", 372345),
        ("  10.45  ", 1045),
        ("DNF", DNF),
        ("dnf", DNF),
        ("Dnf", DNF),
        (" DNF ", DNF),
        ("DNS", DNS),
        ("dns", DNS),
    ],
)
def test_str_to_centiseconds(text: str, expected: int) -> None:
    """Valid time strings and DNF / DNS markers parse to their WCIF integers."""
    assert str_to_centiseconds(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "abc",
        "DNQ",
        "10 s",
        "10.456",  # more than two fractional digits
        "10.",
        ".50",
        "1.2.3",
        "-1.00",
        "1:65.00",  # seconds >= 60 with minutes present
        "1:60",
        "1:60:00",  # minutes >= 60 with hours present
        "1::2",
        "1:2:3:4",
        "1,05.43",
        "10.4a",
    ],
)
def test_str_to_centiseconds_rejects_invalid(text: str) -> None:
    """Garbage and out-of-range components raise ValueError."""
    with pytest.raises(ValueError, match=r"Invalid|must be"):
        str_to_centiseconds(text)


@pytest.mark.parametrize(
    "cs",
    [
        0,
        1,
        5,
        99,
        100,
        1045,
        5999,
        6000,
        6001,
        6543,
        59999,
        60000,
        359999,
        360000,
        372345,
        3_600_000,
        36_000_000,
    ],
)
def test_centiseconds_round_trip_parametrized(cs: int) -> None:
    """str_to_centiseconds inverts centiseconds_to_str for representative values."""
    assert str_to_centiseconds(centiseconds_to_str(cs)) == cs


def test_centiseconds_round_trip_bulk() -> None:
    """Round trip holds across a dense sweep from 0 to just over 1 hour, and a few hours."""
    values = list(range(0, 400_000, 37)) + list(range(0, 1_100_000_000, 9_999_991))
    for cs in values:
        assert str_to_centiseconds(centiseconds_to_str(cs)) == cs, cs


# --- MultiBlindResult: construction -------------------------------------------


@pytest.mark.parametrize(
    ("solved", "attempted", "time_seconds"),
    [(-1, 2, None), (1, -2, None), (1, 2, -1), (1, 2, 99999), (1, 2, 1_000_000)],
)
def test_multi_blind_result_rejects_invalid_fields(
    solved: int, attempted: int, time_seconds: int | None
) -> None:
    """Negative counts and out-of-range times cannot be constructed."""
    with pytest.raises(ValueError):
        MultiBlindResult(solved=solved, attempted=attempted, time_seconds=time_seconds)


def test_multi_blind_result_is_frozen() -> None:
    """MultiBlindResult instances are immutable."""
    result = MultiBlindResult(solved=12, attempted=13, time_seconds=3252)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.solved = 5  # type: ignore[misc]


def test_multi_blind_result_defaults_to_new_style() -> None:
    """is_old_style defaults to False."""
    assert MultiBlindResult(solved=1, attempted=1, time_seconds=60).is_old_style is False


# --- MultiBlindResult: new style (333mbf) decoding ----------------------------


@pytest.mark.parametrize(
    ("value", "solved", "attempted", "time_seconds", "missed", "points"),
    [
        # 12/13 in 54:12, the worked example from the spec
        (880325201, 12, 13, 3252, 1, 11),
        # perfect 2/2 in 5:03
        (970030300, 2, 2, 303, 0, 2),
        # perfect 3/3 in exactly 60:00
        (960360000, 3, 3, 3600, 0, 3),
        # 5/6 with unknown time
        (959999901, 5, 6, None, 1, 4),
        # 10/12 in 16:40, two misses
        (910100002, 10, 12, 1000, 2, 8),
        # perfect 7/7 in 30:15
        (920181500, 7, 7, 1815, 0, 7),
    ],
)
def test_multi_blind_new_style_decoding(
    value: int,
    solved: int,
    attempted: int,
    time_seconds: int | None,
    missed: int,
    points: int,
) -> None:
    """New-style packed integers decode to counts, time, misses and points."""
    result = MultiBlindResult.from_wcif_int(value)
    assert result.is_old_style is False
    assert result.solved == solved
    assert result.attempted == attempted
    assert result.time_seconds == time_seconds
    assert result.missed == missed
    assert result.points == points


def test_multi_blind_worked_example_exact_value() -> None:
    """12/13 in 54:12 is packed as 880325201 (DD=88, time=3252, missed=1)."""
    assert MultiBlindResult(solved=12, attempted=13, time_seconds=3252).to_wcif_int() == 880325201
    assert MultiBlindResult.from_wcif_int(880325201) == MultiBlindResult(
        solved=12, attempted=13, time_seconds=3252
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (880325201, "12/13 54:12"),
        (970030300, "2/2 5:03"),
        (960360000, "3/3 60:00"),
        (910100002, "10/12 16:40"),
        (920181500, "7/7 30:15"),
        (959999901, "5/6 ??:??"),
    ],
)
def test_multi_blind_new_style_formatted(value: int, expected: str) -> None:
    """Formatted output uses unpadded minutes and ??:?? for unknown time."""
    assert MultiBlindResult.from_wcif_int(value).formatted == expected


def test_multi_blind_unknown_time_is_99999_on_the_wire() -> None:
    """Unknown time (None) encodes as the packed value 99999."""
    result = MultiBlindResult(solved=5, attempted=6, time_seconds=None)
    assert result.to_wcif_int() == 959999901
    assert result.formatted == "5/6 ??:??"


def test_multi_blind_zero_missed_has_no_misses() -> None:
    """A perfect result reports zero misses and points equal to solved."""
    result = MultiBlindResult.from_wcif_int(970030300)
    assert result.missed == 0
    assert result.points == result.solved == 2


@pytest.mark.parametrize(("value", "missed"), [(970030300, 0), (880325201, 1), (910100002, 2)])
def test_multi_blind_missed_is_low_two_digits(value: int, missed: int) -> None:
    """The missed count is the last two digits of the packed value."""
    assert value % 100 == missed
    assert MultiBlindResult.from_wcif_int(value).missed == missed


# --- MultiBlindResult: old style (333mbo) ------------------------------------


@pytest.mark.parametrize(
    ("value", "solved", "attempted", "time_seconds"),
    [
        (1871303252, 12, 13, 3252),
        (1970299999, 2, 2, None),
        (1960303600, 3, 3, 3600),
    ],
)
def test_multi_blind_old_style_decoding(
    value: int, solved: int, attempted: int, time_seconds: int | None
) -> None:
    """Legacy 1SSAATTTTT values decode to counts and time."""
    result = MultiBlindResult.from_wcif_int(value)
    assert result.is_old_style is True
    assert result.solved == solved
    assert result.attempted == attempted
    assert result.time_seconds == time_seconds


@pytest.mark.parametrize(
    ("solved", "attempted", "time_seconds", "expected"),
    [
        (12, 13, 3252, 1871303252),
        (2, 2, None, 1970299999),
        (3, 3, 3600, 1960303600),
    ],
)
def test_multi_blind_old_style_encoding(
    solved: int, attempted: int, time_seconds: int | None, expected: int
) -> None:
    """Old-style results encode as 10**9 + (99-solved)*10**7 + attempted*10**5 + time."""
    result = MultiBlindResult(
        solved=solved, attempted=attempted, time_seconds=time_seconds, is_old_style=True
    )
    assert result.to_wcif_int() == expected


def test_multi_blind_old_style_formatted() -> None:
    """Old-style results format the same way as new-style ones."""
    assert MultiBlindResult.from_wcif_int(1871303252).formatted == "12/13 54:12"
    assert MultiBlindResult.from_wcif_int(1970299999).formatted == "2/2 ??:??"


def test_event_id_333mbo_forces_old_style() -> None:
    """Passing event_id '333mbo' selects the legacy layout."""
    result = MultiBlindResult.from_wcif_int(1871303252, event_id="333mbo")
    assert result.is_old_style is True
    assert result.formatted == "12/13 54:12"


def test_large_value_is_old_style_even_for_333mbf() -> None:
    """Values of at least 10**9 are legacy regardless of the event id."""
    result = MultiBlindResult.from_wcif_int(1871303252, event_id="333mbf")
    assert result.is_old_style is True
    assert result.solved == 12


def test_event_id_333mbf_keeps_new_style_for_small_values() -> None:
    """A small value with event id 333mbf decodes with the new-style layout."""
    result = MultiBlindResult.from_wcif_int(880325201, event_id="333mbf")
    assert result.is_old_style is False
    assert result.solved == 12


# --- MultiBlindResult: encoding and round trips ------------------------------


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (MultiBlindResult(solved=12, attempted=13, time_seconds=3252), 880325201),
        (MultiBlindResult(solved=2, attempted=2, time_seconds=303), 970030300),
        (MultiBlindResult(solved=3, attempted=3, time_seconds=3600), 960360000),
        (MultiBlindResult(solved=5, attempted=6, time_seconds=None), 959999901),
        (MultiBlindResult(solved=10, attempted=12, time_seconds=1000), 910100002),
        (MultiBlindResult(solved=7, attempted=7, time_seconds=1815), 920181500),
        (
            MultiBlindResult(solved=12, attempted=13, time_seconds=3252, is_old_style=True),
            1871303252,
        ),
        (
            MultiBlindResult(solved=2, attempted=2, time_seconds=None, is_old_style=True),
            1970299999,
        ),
        (
            MultiBlindResult(solved=3, attempted=3, time_seconds=3600, is_old_style=True),
            1960303600,
        ),
    ],
)
def test_multi_blind_to_wcif_int(result: MultiBlindResult, expected: int) -> None:
    """to_wcif_int packs both layouts to the expected integers."""
    assert result.to_wcif_int() == expected


@pytest.mark.parametrize(
    "result",
    [
        MultiBlindResult(solved=0, attempted=3, time_seconds=60),  # 3 misses, 0 solved
        MultiBlindResult(solved=100, attempted=100, time_seconds=60, is_old_style=True),
        MultiBlindResult(solved=5, attempted=100, time_seconds=60, is_old_style=True),
    ],
)
def test_to_wcif_int_rejects_unencodable(result: MultiBlindResult) -> None:
    """Counts that do not fit the packed layout raise ValueError."""
    with pytest.raises(ValueError, match=r"Cannot encode|must be in"):
        result.to_wcif_int()


@pytest.mark.parametrize("value", [0, -1, -2])
def test_from_wcif_int_rejects_non_results(value: int) -> None:
    """DNF, DNS and skipped values are not multi-blind results."""
    with pytest.raises(ValueError, match="Not a multi-blind result"):
        MultiBlindResult.from_wcif_int(value)


@pytest.mark.parametrize(
    ("value", "points", "missed"),
    [
        (880325201, 11, 1),
        (970030300, 2, 0),
        (910100002, 8, 2),
        (959999901, 4, 1),
        (1871303252, 11, 1),
        (1960303600, 3, 0),
    ],
)
def test_points_and_missed(value: int, points: int, missed: int) -> None:
    """points = solved - missed and missed = attempted - solved."""
    result = MultiBlindResult.from_wcif_int(value)
    assert result.points == points
    assert result.missed == missed
    assert result.points == result.solved - result.missed


def test_points_can_be_negative_when_misses_exceed_solves() -> None:
    """Points are plain arithmetic, so 1 solved out of 5 gives -3."""
    result = MultiBlindResult(solved=1, attempted=5, time_seconds=None)
    assert result.points == -3
    assert result.missed == 4


_NEW_STYLE_SAMPLE: list[int] = [
    1,
    2,
    99,
    100,
    101,
    999,
    1000,
    12345,
    999_999,
    10**7,
    10**7 + 1,
    880325201,
    970030300,
    959999901,
    960360000,
    910100002,
    920181500,
    99 * 10**7 + 99999 * 100 + 99,
    99 * 10**7 + 99998 * 100 + 99,
    99 * 10**7,
]


@pytest.mark.parametrize("value", _NEW_STYLE_SAMPLE)
def test_new_style_round_trip(value: int) -> None:
    """to_wcif_int(from_wcif_int(v)) == v for new-style packed integers."""
    assert MultiBlindResult.from_wcif_int(value).to_wcif_int() == value


def test_new_style_round_trip_bulk() -> None:
    """Round trip holds across a sweep of new-style values below 10**9."""
    for value in range(1, 10**9, 7_919_003):
        assert MultiBlindResult.from_wcif_int(value).to_wcif_int() == value, value


@pytest.mark.parametrize(
    "value",
    [
        1_000_000_000,
        1_000_000_001,
        1871303252,
        1970299999,
        1960303600,
        1_999_999_999,
    ],
)
def test_old_style_round_trip(value: int) -> None:
    """to_wcif_int(from_wcif_int(v)) == v for legacy packed integers."""
    assert MultiBlindResult.from_wcif_int(value).to_wcif_int() == value


def test_old_style_round_trip_bulk() -> None:
    """Round trip holds across a sweep of legacy values in [10**9, 2*10**9)."""
    for value in range(10**9, 2 * 10**9, 13_000_003):
        assert MultiBlindResult.from_wcif_int(value).to_wcif_int() == value, value


def test_old_and_new_style_encode_the_same_result_differently() -> None:
    """The same counts and time pack to different integers in the two layouts."""
    new = MultiBlindResult(solved=12, attempted=13, time_seconds=3252)
    old = MultiBlindResult(solved=12, attempted=13, time_seconds=3252, is_old_style=True)
    assert new.to_wcif_int() == 880325201
    assert old.to_wcif_int() == 1871303252
    assert new.formatted == old.formatted == "12/13 54:12"


# --- format_result ------------------------------------------------------------


@pytest.mark.parametrize(
    "event_id",
    ["333", "222", "333fm", "333mbf", "333mbo", "444bf", "clock"],
)
@pytest.mark.parametrize("is_average", [False, True])
def test_format_result_sentinels_for_every_event(event_id: str, is_average: bool) -> None:
    """DNF, DNS and skipped render the same way for every event and result kind."""
    assert format_result(DNF, event_id, is_average=is_average) == "DNF"
    assert format_result(DNS, event_id, is_average=is_average) == "DNS"
    assert format_result(SKIPPED, event_id, is_average=is_average) == ""


@pytest.mark.parametrize(
    ("result", "event_id", "expected"),
    [
        (1045, "333", "10.45"),
        (5, "222", "0.05"),
        (6543, "444", "1:05.43"),
        (60000, "555", "10:00.00"),
        (360000, "666", "1:00:00.00"),
        (6000, "clock", "1:00.00"),
    ],
)
def test_format_result_clock_events(result: int, event_id: str, expected: str) -> None:
    """Non-special events use centiseconds_to_str for singles."""
    assert format_result(result, event_id) == expected


@pytest.mark.parametrize(
    ("result", "event_id", "expected"),
    [
        (1045, "333", "10.45"),
        (6543, "333", "1:05.43"),
        (60000, "333", "10:00.00"),
    ],
)
def test_format_result_clock_averages(result: int, event_id: str, expected: str) -> None:
    """Averages of clock events format like singles."""
    assert format_result(result, event_id, is_average=True) == expected


@pytest.mark.parametrize(
    ("result", "is_average", "expected"),
    [
        (28, False, "28"),
        (2833, True, "28.33"),
        (3000, True, "30.00"),
        (2800, True, "28.00"),
        (1500, True, "15.00"),
    ],
)
def test_format_result_fmc_single_vs_mean(result: int, is_average: bool, expected: str) -> None:
    """FMC singles are move counts; FMC averages are centimoves (hundredths)."""
    assert format_result(result, "333fm", is_average=is_average) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (880325201, "12/13 54:12"),
        (970030300, "2/2 5:03"),
        (960360000, "3/3 60:00"),
        (959999901, "5/6 ??:??"),
    ],
)
def test_format_result_mbf(value: int, expected: str) -> None:
    """333mbf values go through MultiBlindResult.formatted."""
    assert format_result(value, "333mbf") == expected


def test_format_result_mbo_old_style() -> None:
    """333mbo values use the legacy layout and format the same way."""
    assert format_result(1871303252, "333mbo") == "12/13 54:12"
    assert format_result(1970299999, "333mbo") == "2/2 ??:??"


@pytest.mark.parametrize("result", [-3, -10])
def test_format_result_rejects_other_negatives(result: int) -> None:
    """Negative values other than DNF and DNS are invalid."""
    with pytest.raises(ValueError, match="Invalid result value"):
        format_result(result, "333")
