"""Capture read-only WindowPilot field records for validation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.demo_physical_config import (
    build_windowpilot_drivers,
    load_windowpilot_driver_config,
)
from airtrajectory.layout import LayoutContract
from airtrajectory.windowpilot_field_capture import (
    collect_windowpilot_field_capture,
)


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("runtime_receipt", type=Path)
    parser.add_argument("protocol", type=Path)
    parser.add_argument("windowpilot_config", type=Path)
    parser.add_argument("--validation-id", required=True)
    parser.add_argument(
        "--layout",
        type=Path,
        default=Path("web/data/home_topology.fixed.json"),
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    config = load_windowpilot_driver_config(args.windowpilot_config)
    capture = collect_windowpilot_field_capture(
        layout=LayoutContract.from_file(args.layout),
        config=config,
        drivers=build_windowpilot_drivers(config),
        protocol=_load(args.protocol),
        runtime_receipt=_load(args.runtime_receipt),
        validation_id=args.validation_id,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(capture, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(capture, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
