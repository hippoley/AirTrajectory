"""Import JSONL/CSV site logs into the raw field-capture contract."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.field_capture_import import import_field_capture


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("records", type=Path)
    parser.add_argument(
        "--format",
        choices=("auto", "jsonl", "csv"),
        default="auto",
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    capture = import_field_capture(
        manifest_path=args.manifest,
        records_path=args.records,
        records_format=args.format,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(capture, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(capture, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
