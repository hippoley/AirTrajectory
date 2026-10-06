"""Compile metric-ready layout into deterministic CONTAM writer manifest."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.contam_allocator import allocate_contam_ids
from airtrajectory.contam_ir import compile_contam_ir
from airtrajectory.layout import LayoutContract


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("layout", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    layout = LayoutContract.from_file(args.layout)
    manifest = allocate_contam_ids(compile_contam_ir(layout))
    rendered = json.dumps(manifest, indent=2, sort_keys=True)
    print(rendered)

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
