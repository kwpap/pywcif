"""Save public WCIF documents from the WCA website as test fixtures.

Usage::

    python scripts/snapshot_wcif.py WC2025 Euro2024 [--out tests/fixtures/real]

Each document is written unchanged (pretty-printed) to ``<out>/<CompetitionId>.json``, where
``tests/test_real_wcif.py`` picks it up automatically. Only the public endpoint is used, so no
private data (emails, birthdates) is stored.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pywcif import fetch_wcif_dict

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "real"


def main(argv: list[str] | None = None) -> int:
    """Download each competition id given on the command line; return a process exit code."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("competition_ids", nargs="+", metavar="COMPETITION_ID")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory")
    args = parser.parse_args(argv)

    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    failures = 0
    for competition_id in args.competition_ids:
        try:
            data = fetch_wcif_dict(competition_id, timeout=60.0)
        except Exception as error:  # report and keep going with the other ids
            print(f"{competition_id}: failed ({error})", file=sys.stderr)
            failures += 1
            continue
        target = out / f"{competition_id}.json"
        target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{competition_id}: saved {target} ({len(data.get('persons', []))} persons)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
