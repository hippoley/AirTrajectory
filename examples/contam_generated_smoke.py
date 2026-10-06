"""Load an AirTrajectory-generated PRJ with the real contamxpy runtime."""
from __future__ import annotations

import argparse
import json

from airtrajectory.contam import ContamXSession


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prj")
    parser.add_argument("--expected-zones", type=int, required=True)
    parser.add_argument("--expected-paths", type=int, required=True)
    args = parser.parse_args()

    session = ContamXSession(args.prj)
    try:
        meta = session.setup()
        payload = {
            "marker": "GENERATED_CONTAM_PRJ_LOADED",
            "prj": args.prj,
            "zones": meta["zones"],
            "paths": meta["paths"],
            "time_step_s": meta["time_step_s"],
            "version": meta["version"],
        }
        print(json.dumps(payload, sort_keys=True))
        if meta["zones"] != args.expected_zones:
            raise RuntimeError(
                f"zone count mismatch: {meta['zones']} != {args.expected_zones}"
            )
        if meta["paths"] != args.expected_paths:
            raise RuntimeError(
                f"path count mismatch: {meta['paths']} != {args.expected_paths}"
            )
        return 0
    finally:
        if session.started:
            session.close()


if __name__ == "__main__":
    raise SystemExit(main())
