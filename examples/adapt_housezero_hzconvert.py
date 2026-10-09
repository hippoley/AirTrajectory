"""Convert hzconvert HouseZero CSV rows to AirTrajectory observation receipts."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from airtrajectory.housezero_hzconvert import adapt_hzconvert_row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--topology-id", required=True)
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    if args.limit <= 0:
        raise SystemExit("--limit must be positive")

    receipts = []
    with args.csv_path.open(newline="", encoding="utf-8") as fh:
        for index, row in enumerate(csv.DictReader(fh)):
            if index >= args.limit:
                break
            receipts.append(
                adapt_hzconvert_row(
                    row,
                    topology_id=args.topology_id,
                )
            )

    if not receipts:
        raise SystemExit("CSV contains no data rows")

    rendered = "\n".join(
        json.dumps(receipt, sort_keys=True)
        for receipt in receipts
    ) + "\n"

    if args.out is None:
        print(rendered, end="")
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
        print(
            "HOUSEZERO_HZCONVERT_ADAPTED",
            len(receipts),
            args.out,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
