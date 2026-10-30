# pywcif

Read, query, check and write [WCA](https://www.worldcubeassociation.org) competition data
(WCIF) in Python, with fully typed models.

[![PyPI](https://img.shields.io/pypi/v/pywcif)](https://pypi.org/project/pywcif/)
![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)
[![CI](https://github.com/kwpap/pywcif/actions/workflows/ci.yml/badge.svg)](https://github.com/kwpap/pywcif/actions/workflows/ci.yml)
![License](https://img.shields.io/badge/license-MIT-green)

```bash
pip install pywcif
```

## Quick start

```python
from pywcif import fetch_wcif, format_result

comp = fetch_wcif("WC2025")  # any competition id from the WCA website
print(comp.name, "-", len(comp.get_accepted_competitors()), "competitors")

# Podium of the 3x3x3 final
final = comp.get_event("333").rounds[-1]
podium = sorted((r for r in final.results if r.ranking in (1, 2, 3)), key=lambda r: r.ranking)
for result in podium:
    person = comp.get_person(registrant_id=result.person_id)
    print(result.ranking, person.name, format_result(result.average, "333", is_average=True))
```

Everything is a typed object with autocomplete: `comp.persons`, `comp.events`, `round.results`,
`comp.schedule.venues`, and so on.

## Common tasks

### Load and save WCIF files

```python
from pywcif import dump_wcif, load_wcif

comp = load_wcif("competition.json")  # also accepts a Path, JSON text, bytes or a dict
dump_wcif(comp, "competition-out.json")  # writes the same document back, unchanged
```

Saving is lossless: fields pywcif doesn't know about, such as Groupifier `extensions`, are
written back exactly as they were read.

### Find people

```python
comp.get_person(wca_id="2019PAPA01")  # or registrant_id=..., wca_user_id=...
comp.get_accepted_competitors("333")  # accepted and registered for 3x3x3
comp.get_first_timers()  # competitors without a WCA ID
comp.get_staff()  # people with a role or a staff assignment
```

### A competitor's schedule, in local time

```python
person = comp.get_person(wca_id="2019PAPA01")
for entry in comp.get_person_schedule(person.registrant_id):
    when = entry.local_start.strftime("%a %H:%M")
    print(when, entry.activity.name, entry.assignment.assignment_code)
```

```text
Sat 09:30 3x3x3 Cube Round 1 Group 1 competitor
Sat 11:30 3x3x3 Fewest Moves Round 1 Group 1 competitor
Sat 14:00 3x3x3 Multi-Blind Group 1 competitor
Sat 15:30 3x3x3 Cube Round 2 Group 1 competitor
```

Times are converted from UTC to the venue's timezone.

### Turn result numbers into readable text

WCIF stores results as integers. `format_result` knows each event's encoding:

```python
from pywcif import MultiBlindResult, format_result

format_result(6543, "333")  # '1:05.43'
format_result(-1, "333")  # 'DNF'
format_result(28, "333fm")  # '28'     (single: moves)
format_result(2833, "333fm", is_average=True)  # '28.33'  (mean)
format_result(880325201, "333mbf")  # '12/13 54:12'

MultiBlindResult.from_wcif_int(880325201).points  # 11
```

### Check a competition for mistakes

```python
from pywcif import audit_competition

for issue in audit_competition(comp):
    print(issue.severity, issue.code, issue.message)
```

```text
error CUTOFF_GE_TIMELIMIT Round 333-r1 of event 333 has a cutoff of 60000 cs, which is not below its time limit of 60000 cs
error UNMAPPED_ACTIVITY_ID Eleni Konstantinou is assigned to activity 42, which is not in the schedule
```

The audit never stops loading or saving; it only reports. It checks:

| Code | Severity | What it means |
|---|---|---|
| `CUTOFF_GE_TIMELIMIT` | error | A round's cutoff is not below its time limit. |
| `MISSING_ADVANCEMENT_CONDITION` | error | A non-final round has no advancement condition, or the final has one. |
| `REG_9P1_ADVANCEMENT` | error | Fewer than 25% of competitors would be eliminated (Regulation 9p1). |
| `UNMAPPED_ACTIVITY_ID` | error | Someone is assigned to an activity that isn't in the schedule. |
| `SCHEDULE_CONFLICT` | warning | Someone has two assignments at the same time. |

### Private data (organizers and delegates)

```python
comp = fetch_wcif("YourCompetition2026", oauth_token="...")  # WCA OAuth token
```

This includes emails, birthdates and registration comments. The token is only sent over https.

## Good to know

- **Python names, WCIF JSON.** Attributes are snake_case (`person.wca_id`), JSON keys are
  camelCase (`wcaId`). Both are accepted when loading.
- **New WCA values don't break anything.** Fields such as event ids, roles and assignment codes
  come with enums for autocomplete (`EventId`, `AssignmentCode`, ...), but also accept any other
  string.
- **Use `to_wcif_dict()` / `to_wcif_json()`** to export, not `model_dump(exclude_none=True)`. They
  keep the `null` values WCIF requires and leave out private fields that were never present.
- **Activity codes** such as `333-r1-g2` can be parsed with `ActivityCode.parse()` or
  `activity.parsed_code`.

## Links

- [Changelog](https://github.com/kwpap/pywcif/blob/main/CHANGELOG.md)
- [WCIF specification](https://github.com/thewca/wcif/blob/master/specification.md)
- [Contributing](https://github.com/kwpap/pywcif/blob/main/CONTRIBUTING.md)

MIT licensed.
