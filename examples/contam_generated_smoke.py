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
        session.step()
        flows = {
            str(index): session.path_flow(index)
            for index in range(1, int(meta["paths"]) + 1)
        }
        payload = {
            "marker": "GENERATED_CONTAM_PRJ_EXECUTED",
            "prj": args.prj,
            "zones": meta["zones"],
            "paths": meta["paths"],
            "time_step_s": meta["time_step_s"],
            "version": meta["version"],
            "path_flow_kg_s": flows,
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
        if not any(abs(value) > 1e-12 for value in flows.values()):
            raise RuntimeError("generated CONTAM project produced zero flow on every path")
        return 0
    finally:
        if session.started:
            session.close()


if __name__ == "__main__":
    raise SystemExit(main())
