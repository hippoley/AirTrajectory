"""Project a real CONTAM engineering runtime receipt to a Pascal native-node view model.

Usage:
python examples/project_contam_to_pascal.py layout.json runtime-receipt.json --out projection.json
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from airtrajectory.layout import LayoutContract
from airtrajectory.pascal_result_projection import project_contam_to_pascal


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("layout", type=Path)
    parser.add_argument("runtime_receipt", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    projection = project_contam_to_pascal(
        LayoutContract.from_file(args.layout),
        json.loads(args.runtime_receipt.read_text(encoding="utf-8")),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(projection, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PROJECTION_CREATED_NOT_RENDERED",
                      "projection_sha256": projection["projection_sha256"],
                      "frames": len(projection["frames"]), "output": str(args.out)}, sort_keys=True))


if __name__ == "__main__":
    main()
