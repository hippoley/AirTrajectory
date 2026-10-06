"""Compare a WindowPilot probe against a frozen contract baseline."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.windowpilot_contract_baseline import (
    compare_windowpilot_contract_baseline,
)


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", type=Path)
    parser.add_argument("probe_report", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--require-match", action="store_true")
    args = parser.parse_args()

    result = compare_windowpilot_contract_baseline(
        baseline=_load(args.baseline),
        current_report=_load(args.probe_report),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.require_match and result["status"] != "MATCH":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
