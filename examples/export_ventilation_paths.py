"""Export a portable VentilationPath contract from a topology JSON."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.layout import LayoutContract
from airtrajectory.ventilation_path_contract import (
    build_ventilation_path_contract,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("topology", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    payload = build_ventilation_path_contract(
        LayoutContract.from_file(args.topology)
    )
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    print(rendered)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
