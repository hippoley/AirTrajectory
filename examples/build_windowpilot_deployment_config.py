"""Build a sanitized WindowPilot deployment config draft."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.demo_physical_config import (
    load_windowpilot_driver_config,
)
from airtrajectory.windowpilot_deployment_config_draft import (
    build_windowpilot_deployment_config_draft,
)


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_config", type=Path)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--mapping-profile", type=Path)
    parser.add_argument(
        "--mapping-profile-name",
        default="first-contact",
    )
    parser.add_argument("--config-out", type=Path, required=True)
    parser.add_argument("--receipt-out", type=Path, required=True)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()

    profile = (
        _load(args.mapping_profile)
        if args.mapping_profile is not None
        else None
    )
    config, receipt = build_windowpilot_deployment_config_draft(
        source_config=load_windowpilot_driver_config(
            args.source_config
        ),
        workspace=_load(args.workspace),
        mapping_profile=profile,
        mapping_profile_name=args.mapping_profile_name,
    )

    args.config_out.parent.mkdir(parents=True, exist_ok=True)
    args.config_out.write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.receipt_out.parent.mkdir(parents=True, exist_ok=True)
    args.receipt_out.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    if args.require_ready and receipt["status"] != "READY_FOR_LIVE_PROBE":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
