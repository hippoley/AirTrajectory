"""Probe the installed real contamxpy runtime for state-continuation APIs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.contam_continuation import probe_contamxpy_engine


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prj", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    payload = probe_contamxpy_engine(args.prj)
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    print("CONTAM_CONTINUATION_CAPABILITY_PROBED")
    print(rendered)

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
