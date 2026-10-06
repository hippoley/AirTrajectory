"""Audit engineering readiness of a generated CONTAM provenance receipt."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.contam_engineering_readiness import (
    audit_engineering_readiness,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("provenance", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--require-engineering-ready", action="store_true")
    args = parser.parse_args()

    payload = json.loads(args.provenance.read_text(encoding="utf-8"))
    result = audit_engineering_readiness(payload)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    if args.require_engineering_ready and not result["engineering_ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
