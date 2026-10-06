"""Probe WindowPilot endpoint compatibility without actuator writes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.demo_physical_config import (
    load_windowpilot_driver_config,
)
from airtrajectory.windowpilot_contract_probe import probe_windowpilot_config


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("windowpilot_config", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--require-compatible", action="store_true")
    args = parser.parse_args()

    report = probe_windowpilot_config(
        config=load_windowpilot_driver_config(args.windowpilot_config),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.require_compatible and report["status"] != "COMPATIBLE":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
