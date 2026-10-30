# Real WCIF snapshots

Public WCIF documents downloaded unchanged from the WCA website. Every `*.json` file here is
round-tripped by `tests/test_real_wcif.py` on each test run.

Add one with:

```bash
python scripts/snapshot_wcif.py <CompetitionId>
```

Only the public endpoint is used, so these files contain no emails or birthdates — only data
the WCA already publishes.
