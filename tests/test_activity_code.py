"""Unit tests for pywcif.activity_code."""

from __future__ import annotations

import dataclasses

import pytest

from pywcif.activity_code import ActivityCode

VALID_CODES: list[tuple[str, tuple[str, int | None, int | None, int | None]]] = [
    ("333", ("333", None, None, None)),
    ("333-r1", ("333", 1, None, None)),
    ("333-r1-g2", ("333", 1, 2, None)),
    ("333-r1-a1", ("333", 1, None, 1)),
    ("333-r1-g2-a1", ("333", 1, 2, 1)),
    ("333fm-r1-a2", ("333fm", 1, None, 2)),
    ("222-r2-g3", ("222", 2, 3, None)),
    ("222-g3", ("222", None, 3, None)),
    ("222-a3", ("222", None, None, 3)),
    ("333mbf-r1-g1-a1", ("333mbf", 1, 1, 1)),
    ("3x3x3", ("3x3x3", None, None, None)),
    ("333-r10-g100-a1000", ("333", 10, 100, 1000)),
    ("333-r999999", ("333", 999999, None, None)),
    ("clock-r1", ("clock", 1, None, None)),
    ("777", ("777", None, None, None)),
]

OTHER_CODES: list[str] = [
    "other-lunch",
    "other-tutorial",
    "other-checkin",
    "other-registration",
    "other-x1",
]

INVALID_CODES: list[str] = [
    # empty / stray dashes / trailing dashes
    "",
    "-",
    "--",
    "-r1",
    "333-",
    "333-r1-",
    "333--r1",
    "333-r1--g2",
    # out-of-order tokens
    "333-g1-r1",
    "333-a1-g1",
    "333-a1-r1",
    "333-g2-a1-r1",
    # duplicate tokens
    "333-r1-r2",
    "333-g1-g1",
    "333-a1-a1",
    "333-r1-g1-r1",
    "333fm-r1-a2-a3",
    # unknown tokens
    "333-x1",
    "333-q",
    "333-r1-z2",
    "333-n1",
    "333-R1",
    "333-G2",
    "333-A1",
    "333-rr1",
    # non-numeric / zero / negative / malformed numbers
    "333-r0",
    "333-g0",
    "333-a0",
    "333-r0-g1",
    "333-rx",
    "333-r",
    "333-g",
    "333-a",
    "333-r-1",
    "333-r+1",
    "333-r1.5",
    "333-r1a",
    "333-r 1",
    "333-r01",
    "333-g02",
    "333-r1-a00",
    "333-r\u0661",  # Arabic-Indic digit one
    # uppercase / garbage event ids
    "333FM",
    "333Fm",
    "333FM-r1",
    "3-3-3",
    "333_fm",
    "333!",
    "333.fm",
    "333/fm",
    " 333",
    "333 ",
    "333 -r1",
    "333\n",
    "̳",
    "-r1-g1",
    # non-competition codes with a bad name or with numbers
    "other-",
    "other-Lunch",
    "other-LUNCH",
    "other-lunch-r1",
    "other-lunch-g1-a1",
    "other-lunch ",
    "other-lunch!",
    "other-lunch-",
    "other-lunch--x",
]


@pytest.mark.parametrize(("code", "expected"), VALID_CODES)
def test_parse_valid_competition_codes(
    code: str, expected: tuple[str, int | None, int | None, int | None]
) -> None:
    parsed = ActivityCode.parse(code)
    assert (
        parsed.event_id,
        parsed.round_number,
        parsed.group_number,
        parsed.attempt_number,
    ) == expected


@pytest.mark.parametrize("code", OTHER_CODES)
def test_parse_other_codes_keeps_whole_string_as_event_id(code: str) -> None:
    parsed = ActivityCode.parse(code)
    assert parsed.event_id == code
    assert parsed.round_number is None
    assert parsed.group_number is None
    assert parsed.attempt_number is None
    assert parsed.is_official_event is False


def test_parse_returns_activity_code_instance() -> None:
    assert isinstance(ActivityCode.parse("333-r1"), ActivityCode)


@pytest.mark.parametrize("code", [code for code, _ in VALID_CODES] + OTHER_CODES)
def test_str_round_trips_canonical_codes(code: str) -> None:
    assert str(ActivityCode.parse(code)) == code


@pytest.mark.parametrize("code", [code for code, _ in VALID_CODES] + OTHER_CODES)
def test_parse_of_str_is_identity(code: str) -> None:
    parsed = ActivityCode.parse(code)
    assert ActivityCode.parse(str(parsed)) == parsed


def test_str_renders_gaps_in_token_sequence() -> None:
    assert str(ActivityCode("333", round_number=1, attempt_number=2)) == "333-r1-a2"
    assert str(ActivityCode("333", group_number=4)) == "333-g4"


@pytest.mark.parametrize("code", INVALID_CODES)
def test_parse_rejects_invalid_codes(code: str) -> None:
    with pytest.raises(ValueError):
        ActivityCode.parse(code)


def test_parse_error_names_the_bad_token() -> None:
    with pytest.raises(ValueError, match="'r1'"):
        ActivityCode.parse("333-g1-r1")
    with pytest.raises(ValueError, match="'x1'"):
        ActivityCode.parse("333-x1")


def test_parse_empty_string_message() -> None:
    with pytest.raises(ValueError, match="empty"):
        ActivityCode.parse("")


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("333", True),
        ("333fm-r1", True),
        ("222-r2-g3", True),
        ("other-lunch", False),
        ("other-tutorial", False),
        ("other-checkin", False),
    ],
)
def test_is_official_event(code: str, expected: bool) -> None:
    assert ActivityCode.parse(code).is_official_event is expected


def test_is_official_event_false_iff_prefix_other() -> None:
    assert ActivityCode("other-lunch").is_official_event is False
    assert ActivityCode("333").is_official_event is True
    assert ActivityCode("others").is_official_event is True


@pytest.mark.parametrize(
    ("parent", "child"),
    [
        ("333", "333-r1"),
        ("333", "333-r1-g2"),
        ("333", "333-r1-g2-a1"),
        ("333", "333-g2"),
        ("333", "333-a1"),
        ("333", "333-g2-a1"),
        ("333-r1", "333-r1-g2"),
        ("333-r1", "333-r1-a1"),
        ("333-r1", "333-r1-g2-a1"),
        ("333-r1-g2", "333-r1-g2-a1"),
        ("333-g2", "333-r1-g2"),
        ("333-g2", "333-r1-g2-a1"),
        ("333-a1", "333-r1-g2-a1"),
        ("333-r1-a1", "333-r1-g2-a1"),
        ("333fm", "333fm-r1-a2"),
        ("222-r2", "222-r2-g3"),
    ],
)
def test_is_parent_of_positive(parent: str, child: str) -> None:
    assert ActivityCode.parse(parent).is_parent_of(ActivityCode.parse(child)) is True


@pytest.mark.parametrize(
    ("code", "other"),
    [
        # Not parent of itself
        ("333", "333"),
        ("333-r1", "333-r1"),
        ("333-r1-g2-a1", "333-r1-g2-a1"),
        # Different round numbers
        ("333-r1", "333-r2-g1"),
        ("333-r1", "333-r2"),
        ("333-r1-g1", "333-r2-g1"),
        # Child is not parent of its parent
        ("333-r1", "333"),
        ("333-r1-g2", "333-r1"),
        ("333-r1-a1", "333-r1"),
        ("333-r1-g2-a1", "333-r1-g2"),
        # Different event ids
        ("333", "222"),
        ("333", "222-r1"),
        ("333-r1", "333fm-r1"),
        ("333fm", "333-r1"),
        ("333", "3333-r1"),
        ("33", "333-r1"),
        # Conflicting group / attempt numbers
        ("333-r1-g2", "333-r1-g3"),
        ("333-g2", "333-r1-g3"),
        ("333-r1-g2", "333-r1-a2"),
        ("333-a1", "333-r1-g2-a2"),
        ("333-g1-a1", "333-r1-g2-a1"),
        ("333-a2", "333-r1-g2-a1"),
    ],
)
def test_is_parent_of_negative(code: str, other: str) -> None:
    assert ActivityCode.parse(code).is_parent_of(ActivityCode.parse(other)) is False


def test_child_is_not_parent_of_broader_code_for_each_field() -> None:
    child = ActivityCode.parse("333-r1-g2-a1")
    for broader in ("333", "333-r1", "333-r1-g2", "333-r1-a1", "333-g2", "333-a1"):
        assert ActivityCode.parse(broader).is_parent_of(child) is True
        assert child.is_parent_of(ActivityCode.parse(broader)) is False


@pytest.mark.parametrize(
    ("code", "other"),
    [
        ("other-lunch", "other-lunch"),
        ("other-lunch", "other-tutorial"),
        ("other-lunch", "333"),
        ("333", "other-lunch"),
        ("333-r1", "other-lunch"),
        ("other-tutorial", "other-lunch"),
    ],
)
def test_other_codes_are_never_parents(code: str, other: str) -> None:
    assert ActivityCode.parse(code).is_parent_of(ActivityCode.parse(other)) is False


def test_is_parent_of_is_not_symmetric() -> None:
    broad = ActivityCode.parse("333")
    narrow = ActivityCode.parse("333-r1")
    assert broad.is_parent_of(narrow) is True
    assert narrow.is_parent_of(broad) is False


def test_equal_codes_from_different_inputs_are_equal() -> None:
    assert ActivityCode.parse("333-r1") == ActivityCode("333", round_number=1)
    assert ActivityCode.parse("333-r1") != ActivityCode.parse("333-r2")


def test_instances_are_hashable_and_usable_as_dict_keys() -> None:
    mapping = {
        ActivityCode.parse("333-r1-g2"): "first",
        ActivityCode.parse("333"): "event",
    }
    assert mapping[ActivityCode("333", round_number=1, group_number=2)] == "first"
    assert mapping[ActivityCode.parse("333")] == "event"


def test_instances_are_usable_in_sets() -> None:
    codes = {
        ActivityCode.parse("333-r1"),
        ActivityCode.parse("333-r1"),
        ActivityCode.parse("333-r2"),
    }
    assert len(codes) == 2
    assert ActivityCode("333", round_number=1) in codes
    assert ActivityCode.parse("333-r3") not in codes


def test_equal_codes_have_equal_hashes() -> None:
    assert hash(ActivityCode.parse("333-r1-a2")) == hash(ActivityCode("333", 1, None, 2))


def test_assignment_to_field_raises_frozen_error() -> None:
    code = ActivityCode.parse("333-r1")
    with pytest.raises(dataclasses.FrozenInstanceError):
        code.round_number = 2  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        code.event_id = "222"  # type: ignore[misc]
    assert str(code) == "333-r1"


def test_is_official_event_is_read_only() -> None:
    code = ActivityCode.parse("333")
    with pytest.raises(AttributeError):
        code.is_official_event = False  # type: ignore[misc]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"event_id": ""},
        {"event_id": "333FM"},
        {"event_id": "333-r1"},
        {"event_id": "3 3 3"},
        {"event_id": "333", "round_number": 0},
        {"event_id": "333", "group_number": -1},
        {"event_id": "333", "attempt_number": 0},
        {"event_id": "other-"},
        {"event_id": "other-Lunch"},
        {"event_id": "other-lunch", "round_number": 1},
        {"event_id": "other-lunch", "attempt_number": 1},
    ],
)
def test_direct_construction_is_validated(kwargs: dict[str, str | int]) -> None:
    with pytest.raises(ValueError):
        ActivityCode(**kwargs)  # type: ignore[arg-type]


def test_direct_construction_accepts_valid_fields() -> None:
    assert str(ActivityCode("333", 1, 2, 3)) == "333-r1-g2-a3"
    assert str(ActivityCode("other-lunch")) == "other-lunch"


def test_default_numbers_are_none() -> None:
    code = ActivityCode("333")
    assert code.round_number is None
    assert code.group_number is None
    assert code.attempt_number is None
