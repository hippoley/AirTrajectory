"""Compile raw timestamped field events into validation samples."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.contam_field_capture import compile_field_capture_bundle
from airtrajectory.layout import LayoutContract


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("runtime_receipt", type=Path)
    parser.add_argument("protocol", type=Path)
    parser.add_argument("capture", type=Path)
    parser.add_argument(
        "--layout",
        type=Path,
        default=Path("web/data/home_topology.fixed.json"),
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    result = compile_field_capture_bundle(
        layout=LayoutContract.from_file(args.layout),
        runtime_receipt=_load(args.runtime_receipt),
        protocol=_load(args.protocol),
        capture=_load(args.capture),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
