"""Capture exact raw WindowPilot GET payload bytes for offline mapping."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.demo_physical_config import (
    load_windowpilot_driver_config,
)
from airtrajectory.windowpilot_first_contact import (
    capture_windowpilot_first_contact,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("windowpilot_config", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--manifest-out", type=Path, required=True)
    args = parser.parse_args()

    config = load_windowpilot_driver_config(args.windowpilot_config)
    manifest, captures = capture_windowpilot_first_contact(
        config=config,
    )

    for endpoint_id, files in captures.items():
        endpoint_dir = args.out_dir / endpoint_id
        endpoint_dir.mkdir(parents=True, exist_ok=True)
        for filename, body in files.items():
            (endpoint_dir / filename).write_bytes(body)

    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
