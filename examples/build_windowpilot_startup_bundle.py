"""Build a replayable WindowPilot read-only startup evidence bundle."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.windowpilot_startup_bundle import (
    build_windowpilot_startup_bundle,
)


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", type=Path)
    parser.add_argument("probe_report", type=Path)
    parser.add_argument("comparison", type=Path)
    parser.add_argument("preflight", type=Path)
    parser.add_argument("--bundle-id", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    bundle = build_windowpilot_startup_bundle(
        baseline=_load(args.baseline),
        probe_report=_load(args.probe_report),
        comparison=_load(args.comparison),
        preflight=_load(args.preflight),
        bundle_id=args.bundle_id,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(bundle, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(bundle, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
