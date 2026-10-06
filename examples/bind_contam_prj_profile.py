"""Bind explicit PRJ serialization fields onto a forced CONTAM manifest."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.contam_prj_profile import bind_prj_serialization_profile
from airtrajectory.contam_prj_readiness import audit_prj_readiness


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("forced_manifest", type=Path)
    parser.add_argument("profile", type=Path)
    parser.add_argument("--require-engineering-validated", action="store_true")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--readiness-out", type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.forced_manifest.read_text(encoding="utf-8"))
    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    profiled = bind_prj_serialization_profile(
        manifest,
        profile,
        require_engineering_validated=args.require_engineering_validated,
    )
    readiness = audit_prj_readiness(profiled)

    rendered = json.dumps(profiled, indent=2, sort_keys=True)
    print(rendered)

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    if args.readiness_out is not None:
        args.readiness_out.parent.mkdir(parents=True, exist_ok=True)
        args.readiness_out.write_text(
            json.dumps(readiness, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return 0 if readiness["prj_serialization_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
