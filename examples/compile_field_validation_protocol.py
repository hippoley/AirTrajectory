"""Validate and freeze an approved field-validation protocol."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.contam_field_validation import (
    validate_field_validation_protocol,
)
from airtrajectory.layout import LayoutContract


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("protocol", type=Path)
    parser.add_argument(
        "--layout",
        type=Path,
        default=Path("web/data/home_topology.fixed.json"),
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    normalized = validate_field_validation_protocol(
        LayoutContract.from_file(args.layout),
        json.loads(args.protocol.read_text(encoding="utf-8")),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(normalized, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(normalized, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
