# Contributing to pywcif

## Setup and checks

```bash
pip install -e ".[dev]"
ruff format .
ruff check .
mypy src tests
pytest
```

CI runs the same checks on Python 3.10–3.13.

## Tests against real WCIFs

`tests/test_real_wcif.py` checks that real WCA documents survive a lossless round-trip:

- **Recorded snapshots** in `tests/fixtures/real/*.json` run with every `pytest`, and in CI.
  Add one with `python scripts/snapshot_wcif.py <CompetitionId>`.
- **Live tests** download fresh WCIFs and only run when asked: `pytest --run-live`. Pick
  competitions with `PYWCIF_LIVE_COMPETITIONS="WC2025,Euro2024"`. The *Live WCIF* GitHub
  workflow runs them weekly, on pull requests that touch `src/`, and on demand.

A failing round-trip lists every differing JSON path, grouped by pattern, so one run shows
every distinct mismatch.

## Design rules

- WCA regulation checks belong in `audit.py`, never in model validators. An incomplete
  competition must always load.
- Enum-typed fields are `EnumType | str`, so new WCA values never fail validation.
- Fields that the WCA website sometimes leaves out go in the model's
  `_OPTIONAL_OMITTABLE_FIELDS`, so a load followed by a dump stays lossless.

## Releasing

1. Bump `__version__` in `src/pywcif/__init__.py` and move the `Unreleased` notes in
   `CHANGELOG.md` under the new version.
2. Merge to `main`, then tag and push the version: `git tag vX.Y.Z && git push origin vX.Y.Z`.
3. The *Release* workflow:
   - checks that the tag matches `__version__`;
   - runs the tests against the built wheel;
   - publishes to PyPI through Trusted Publishing (no stored token);
   - creates the GitHub release from the changelog.

   Run the workflow by hand to publish to TestPyPI first.
