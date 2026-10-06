"""Evaluate saved WindowPilot GET payloads against a mapping profile."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.windowpilot_mapping_fixture import (
    evaluate_windowpilot_mapping_files,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mapping_profile", type=Path)
    parser.add_argument("capabilities_json", type=Path)
    parser.add_argument("physical_readiness_json", type=Path)
    parser.add_argument("state_json", type=Path)
    parser.add_argument("--fixture-id", default="offline-windowpilot-fixture")
    parser.add_argument("--report-out", type=Path, required=True)
    parser.add_argument("--canonical-out", type=Path)
    parser.add_argument("--require-compatible", action="store_true")
    args = parser.parse_args()

    report, canonical = evaluate_windowpilot_mapping_files(
        profile_bytes=args.mapping_profile.read_bytes(),
        capabilities_bytes=args.capabilities_json.read_bytes(),
        physical_readiness_bytes=args.physical_readiness_json.read_bytes(),
        state_bytes=args.state_json.read_bytes(),
        fixture_id=args.fixture_id,
    )

    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.canonical_out is not None:
        args.canonical_out.parent.mkdir(parents=True, exist_ok=True)
        args.canonical_out.write_text(
            json.dumps(canonical, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    print(json.dumps(report, indent=2, sort_keys=True))
    if args.require_compatible and report["status"] != "COMPATIBLE":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
