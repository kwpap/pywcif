# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). Until 1.0, minor versions may
include breaking changes.

## [Unreleased]

## [0.1.1] - 2026-10-30

### Changed

- Rewrote the README around short usage examples, so the PyPI page starts with how to use the
  library. Development and release notes moved to `CONTRIBUTING.md`.
- Clearer PyPI summary and more search keywords (speedcubing, Rubik's cube, WCA, Groupifier,
  WCA Live, ...), so people can find the package.

### Security

- Added `SECURITY.md` with a private reporting channel, Dependabot updates for GitHub Actions
  and Python dependencies, and `persist-credentials: false` on every workflow checkout.

## [0.1.0] - 2026-10-30

First release.

### Added

- Pydantic v2 models for every WCIF v1.2 entity, from `Competition` down to `Attempt`, with
  camelCase JSON keys and snake_case attributes.
- Lossless round-trip: `to_wcif_dict()` / `to_wcif_json()` keep required `null` keys, leave out
  private fields the input did not have, and preserve unknown keys and extensions. Verified
  against real WCA documents (WC2007, WC2019, WC2023, Euro2024, WC2025).
- Forward-compatible enums (`EventId`, `RoundFormat`, `AssignmentCode`, `RegistrationStatus`,
  ...): fields accept unknown strings, so new WCA events or custom codes never fail validation.
- `ActivityCode` for parsing, formatting and comparing activity codes such as `333-r1-g2`.
- Result decoding: `format_result`, `centiseconds_to_str`, `str_to_centiseconds`, FMC single
  vs. mean, and `MultiBlindResult` for new-style `333mbf` and old-style `333mbo` values.
- `Competition` query helpers: persons, accepted competitors, first-timers, staff, events,
  rounds, activities, and per-person schedules in the venue's local timezone.
- `audit_competition` with five checks: `CUTOFF_GE_TIMELIMIT`,
  `MISSING_ADVANCEMENT_CONDITION`, `REG_9P1_ADVANCEMENT`, `UNMAPPED_ACTIVITY_ID` and
  `SCHEDULE_CONFLICT`.
- `fetch_wcif` / `fetch_wcif_dict` for the public and OAuth WCA endpoints, using only the
  standard library, plus `load_wcif` and `dump_wcif`.

### Security

- OAuth tokens are never forwarded on HTTP redirects and are never sent over plain http,
  except to loopback hosts.

[Unreleased]: https://github.com/kwpap/pywcif/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/kwpap/pywcif/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/kwpap/pywcif/releases/tag/v0.1.0
