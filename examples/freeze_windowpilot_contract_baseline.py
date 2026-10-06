"""Freeze a compatible WindowPilot probe as a contract baseline."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.windowpilot_contract_baseline import (
    freeze_windowpilot_contract_baseline,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("probe_report", type=Path)
    parser.add_argument("--baseline-id", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    report = json.loads(args.probe_report.read_text(encoding="utf-8"))
    baseline = freeze_windowpilot_contract_baseline(
        report,
        baseline_id=args.baseline_id,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(baseline, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(baseline, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
