# pywcif

[![CI](https://github.com/kwpap/pywcif/actions/workflows/ci.yml/badge.svg)](https://github.com/kwpap/pywcif/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)
![Mypy](https://img.shields.io/badge/mypy-strict-blueviolet)
![Ruff](https://img.shields.io/badge/lint-ruff-46a758)

Typed Pydantic v2 models and utilities for the World Cube Association Competition Interchange
Format (WCIF v1.2).

## Installation

```bash
pip install pywcif
```

## Features

- **Typed models**: Pydantic v2 models for the WCIF v1.2 objects (competition, persons, events,
  rounds, results, schedule). Attributes are snake_case and map to the camelCase JSON keys.
- **Lossless round-trip**: unknown keys, such as third-party `extensions` data, are kept on load
  and written back on dump.
- **Forward-compatible enums**: enums such as `EventId` and `RoundFormat` for autocomplete. Fields
  still accept strings the enum does not list.
- **Activity codes**: parse, validate and compare codes such as `333-r1-g2-a1`.
- **Result decoding**: centisecond times, DNF/DNS markers, fewest-moves results and packed
  multi-blind results.
- **Regulation audit**: `audit_competition` reports WCA regulation problems and schedule conflicts.
- **Zero-dependency HTTP fetch**: `fetch_wcif` uses only `urllib.request`. Pydantic is the only
  runtime dependency.

Requires Python 3.10 or newer.

## Quickstart

Fetch the public WCIF of a competition:

```python
from pywcif import fetch_wcif

comp = fetch_wcif("YourCompetition2026")  # any WCA competition id
print(comp.name, len(comp.persons))
```

Fetch the private WCIF with an OAuth token that has access to the competition:

```python
import os

from pywcif import fetch_wcif

comp = fetch_wcif("YourCompetition2026", oauth_token=os.environ["WCA_OAUTH_TOKEN"])
```

Load a WCIF file. `load_wcif` also accepts a `Path`, JSON `bytes`, a JSON string or a `dict`:

```python
from pywcif import load_wcif

comp = load_wcif("tests/fixtures/sample_competition.json")
```

Dump a competition back to JSON:

```python
from pywcif import dump_wcif

text = dump_wcif(comp)  # indented JSON string (indent=2)
dump_wcif(comp, "competition.json", indent=None)  # compact, and also written to a file
```

## Querying

The helpers below use the sample competition in `tests/fixtures/sample_competition.json`.

```python
from pywcif import load_wcif

comp = load_wcif("tests/fixtures/sample_competition.json")

person = comp.get_person(registrant_id=1001)  # also wca_id=..., wca_user_id=...; None if absent
print(person.name, person.wca_id)

print([p.name for p in comp.get_accepted_competitors("333")])  # accepted and competing in 333
print([p.name for p in comp.get_first_timers()])  # accepted, no WCA ID
print([p.name for p in comp.get_staff()])  # has a role or a staff assignment

rnd = comp.get_round("333-r1")
print(rnd.id, rnd.format, len(rnd.results))
```

```text
Nikolaos Papadakis 2019PAPA01
['Nikolaos Papadakis', 'Eleni Konstantinou', 'Lukas Brandt', 'Ayaka Tanaka', 'Dimitris Vlachos']
['Dimitris Vlachos']
['Eleni Konstantinou', 'Georgios Makris']
333-r1 a 5
```

`get_event(event_id)`, `get_round(round_id)` and `get_activity(activity_id)` return `None` when
nothing matches.

## Schedules

`iter_activities()` yields `(venue, room, activity)` depth first, with each parent before its
children. `get_person_schedule()` returns one person's assignments in the venue's local time,
sorted by start:

```python
from pywcif import load_wcif

comp = load_wcif("tests/fixtures/sample_competition.json")

for entry in comp.get_person_schedule(1001):  # registrant id
    start = entry.local_start.strftime("%H:%M")
    end = entry.local_end.strftime("%H:%M")
    print(
        f"{start}-{end}  {entry.activity.name} ({entry.room.name})"
        f"  {entry.assignment.assignment_code}"
    )
```

```text
09:30-10:30  3x3x3 Cube Round 1 Group 1 (Main Hall)  competitor
11:30-12:30  3x3x3 Fewest Moves Round 1 Group 1 (Side Room)  competitor
14:00-15:00  3x3x3 Multi-Blind Group 1 (Side Room)  competitor
15:30-16:15  3x3x3 Cube Round 2 Group 1 (Main Hall)  competitor
```

The sample venue is in `Europe/Athens`, so the stored UTC times (06:30Z) print as local time
(09:30 in May, UTC+3). Each entry also has `entry.venue`, `entry.room` and the raw
`entry.assignment`.

`ActivityCode` parses the codes that schedule activities use:

```python
from pywcif import ActivityCode

code = ActivityCode.parse("333-r1-g2")
print(code.event_id, code.round_number, code.group_number, code.attempt_number)  # 333 1 2 None
print(str(ActivityCode.parse("333-r1-g2-a1")))  # 333-r1-g2-a1
print(ActivityCode.parse("other-lunch").is_official_event)  # False

print(ActivityCode.parse("333").is_parent_of(ActivityCode.parse("333-r1")))  # True
print(ActivityCode.parse("333-r1").is_parent_of(ActivityCode.parse("333-r2-g1")))  # False

ActivityCode.parse("333-g1-r1")
# ValueError: token 'r1' is out of order in activity code '333-g1-r1'
```

Each `Activity` has a `parsed_code` property that returns its `ActivityCode`.

## Results

WCIF stores results as integers: `-1` is DNF, `-2` is DNS and `0` is skipped. Times are in
centiseconds.

```python
from pywcif import MultiBlindResult, centiseconds_to_str, format_result, str_to_centiseconds

print(format_result(6543, "333"))  # 1:05.43
print(format_result(-1, "333"))  # DNF
print(format_result(-2, "333"))  # DNS
print(format_result(28, "333fm"))  # 28       (single: move count)
print(format_result(2833, "333fm", is_average=True))  # 28.33    (mean: centimoves)

mbld = MultiBlindResult.from_wcif_int(880325201)
print(mbld.solved, mbld.attempted, mbld.points)  # 12 13 11
print(mbld.formatted)  # 12/13 54:12
print(format_result(880325201, "333mbf"))  # 12/13 54:12
print(mbld.to_wcif_int())  # 880325201

print(centiseconds_to_str(6543))  # 1:05.43
print(str_to_centiseconds("1:05.43"))  # 6543
print(str_to_centiseconds("DNF"))  # -1
```

`MultiBlindResult.from_wcif_int` decodes both the current `333mbf` packing and the legacy
`333mbo` packing. `to_wcif_int()` is its exact inverse.

## Auditing

`audit_competition` returns a list of `AuditIssue` objects. Each one has `code`, `severity`
(`"error"` or `"warning"`), `message` and a `context` dict with the ids involved.

```python
from pywcif import audit_competition, load_wcif

comp = load_wcif("tests/fixtures/sample_competition.json")

for issue in audit_competition(comp):
    print(f"{issue.severity:<8} {issue.code}: {issue.message}")
```

The sample competition is clean, so the loop prints nothing for it.

| Code | Severity | Meaning |
|---|---|---|
| `CUTOFF_GE_TIMELIMIT` | error | A round's cutoff is not below its time limit. Only checked when the time limit is not cumulative. |
| `MISSING_ADVANCEMENT_CONDITION` | error | A non-final round has no advancement condition, or the final round has one. |
| `REG_9P1_ADVANCEMENT` | error | Regulation 9p1: at least 25% of competitors must be eliminated between rounds. Flags a percent advancement above 75, or a first-round ranking above 75% of the event's accepted competitors. |
| `UNMAPPED_ACTIVITY_ID` | error | A person is assigned to an activity id that is not in the schedule. |
| `SCHEDULE_CONFLICT` | warning | A person has two assignments whose time intervals overlap. Parent and child activities are not reported. |

## Serialization semantics

- **Keys.** Attributes are snake_case (`wca_id`) and JSON keys are camelCase (`wcaId`). Both
  spellings are accepted on input. `to_wcif_dict()` and `to_wcif_json()` write camelCase.
- **Required nullable fields** are always written, as `null` when empty. Examples: `wcaId`,
  `registrantId`, `avatar`, `registration`, `cutoff`, `timeLimit`, `advancementCondition`,
  `ranking`, `stationNumber`, `scrambleSetId`, and the competition's `competitorLimit`.
- **Optional private fields** are omitted when they are unset. An explicit `null` in the input is
  kept. Examples: `email`, `birthdate`, a registration's `guests`, `comments` and
  `administrativeNotes`, an attempt's `reconstruction`, a round's `scrambleSets`, an event's
  `competitorLimit` and `qualification`, and a competition's `series`.
- **Unknown keys** are kept (`extra="allow"`) and written back. They are available in
  `model_extra`.
- **Enum fields accept unknown strings.** Fields are typed `EnumType | str`, so a role or
  assignment code added after this release still loads and round-trips.

Use `to_wcif_dict()` or `to_wcif_json()` rather than `model_dump(exclude_none=True)`, which would
drop the required nulls.

```python
from pywcif import Person

person = Person.model_validate(
    {
        "name": "Ada Example",
        "wcaUserId": 1,
        "countryIso2": "GR",
        "gender": "f",
        "email": None,
        "futureField": 42,
        "roles": ["mentor"],
    }
)
data = person.to_wcif_dict()
print(data["email"])  # None   (explicit null is kept)
print("birthdate" in data)  # False  (never set, so omitted)
print(data["wcaId"])  # None   (required nullable, always written)
print(data["futureField"], data["roles"])  # 42 ['mentor']
```

## Development

```bash
pip install -e ".[dev]"
ruff format .
ruff check .
mypy src tests
pytest
```

### Tests against real WCIFs

`tests/test_real_wcif.py` checks that real WCA documents survive a lossless round-trip:

- **Recorded snapshots** in `tests/fixtures/real/*.json` run with every `pytest` (and in CI).
  Add one with `python scripts/snapshot_wcif.py <CompetitionId>`.
- **Live tests** download fresh WCIFs and are opt-in: `pytest --run-live`. Pick competitions
  with `PYWCIF_LIVE_COMPETITIONS="WC2025,Euro2024"`. The separate *Live WCIF* GitHub workflow
  runs them weekly, on pull requests touching `src/`, and on demand.
