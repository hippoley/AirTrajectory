"""Capture a complete WindowPilot first-contact workspace in one command."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.demo_physical_config import (
    load_windowpilot_driver_config,
)
from airtrajectory.windowpilot_first_contact_workspace import (
    build_windowpilot_first_contact_workspace,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("windowpilot_config", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--workspace-out", type=Path, required=True)
    parser.add_argument("--mapping-profile", type=Path)
    parser.add_argument("--require-compatible", action="store_true")
    args = parser.parse_args()

    profile_bytes = (
        args.mapping_profile.read_bytes()
        if args.mapping_profile is not None
        else None
    )
    workspace, captures, evaluations = (
        build_windowpilot_first_contact_workspace(
            config=load_windowpilot_driver_config(
                args.windowpilot_config
            ),
            mapping_profile_bytes=profile_bytes,
        )
    )

    for endpoint_id, files in captures.items():
        endpoint_dir = args.out_dir / endpoint_id
        endpoint_dir.mkdir(parents=True, exist_ok=True)
        for filename, body in files.items():
            (endpoint_dir / filename).write_bytes(body)

    for endpoint_id, value in evaluations.items():
        endpoint_dir = args.out_dir / endpoint_id
        endpoint_dir.mkdir(parents=True, exist_ok=True)
        (endpoint_dir / "mapping-evaluation.json").write_text(
            json.dumps(
                value["report"],
                indent=2,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
        (endpoint_dir / "canonical-payloads.json").write_text(
            json.dumps(
                value["canonical"],
                indent=2,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )

    args.workspace_out.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    args.workspace_out.write_text(
        json.dumps(workspace, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(workspace, indent=2, sort_keys=True))

    if (
        args.require_compatible
        and workspace["status"] != "CAPTURED_AND_COMPATIBLE"
    ):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
