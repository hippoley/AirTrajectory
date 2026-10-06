"""Audit whether a forced CONTAM manifest is ready for concrete PRJ writing."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.contam_prj_readiness import audit_prj_readiness


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    result = audit_prj_readiness(manifest)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")

    if args.require_ready and not result["prj_serialization_ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
