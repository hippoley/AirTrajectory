"""Merge multiple verified WindowPilot terminal receipts into one origin."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.physical_origin import merge_physical_next_origins


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("current_origin", type=Path)
    parser.add_argument("measurement_manifest", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument(
        "--max-measurement-skew-s",
        type=float,
        default=10.0,
        help="Reject merged physical measurements whose sensor timestamps span more than this many seconds.",
    )
    args = parser.parse_args()

    current = json.loads(args.current_origin.read_text(encoding="utf-8"))
    manifest = json.loads(
        args.measurement_manifest.read_text(encoding="utf-8")
    )
    measurements = manifest.get("measurements")
    if not isinstance(measurements, list):
        raise ValueError("measurement manifest requires measurements list")

    normalized = []
    for row in measurements:
        reconcile = row.get("reconcile")
        if isinstance(reconcile, str):
            reconcile = json.loads(
                Path(reconcile).read_text(encoding="utf-8")
            )
        normalized.append(
            {
                "zone_id": row.get("zone_id"),
                "reconcile": reconcile,
            }
        )

    receipt = merge_physical_next_origins(
        current_origin=current,
        measurements=normalized,
        max_measurement_skew_s=args.max_measurement_skew_s,
    )
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
