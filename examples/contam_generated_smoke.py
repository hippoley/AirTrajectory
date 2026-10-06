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
        if int(meta.get("input_controls") or 0) != 3:
            raise RuntimeError(
                f"expected 3 external input controls, got {meta.get('input_controls')}"
            )

        expected_names={"W1_open","W2_open","W3_open"}
        actual_names=set(meta.get("input_control_names") or [])
        if actual_names != expected_names:
            raise RuntimeError(
                f"unexpected input control names: {sorted(actual_names)}"
            )
        w1_index=session.input_control_index("W1_open")
        session.set_named_input_control("W1_open", 1.0)
        session.step()
        open_flows = {
            str(index): session.path_flow(index)
            for index in range(1, int(meta["paths"]) + 1)
        }

        session.set_named_input_control("W1_open", 0.0)
        session.step()
        closed_flows = {
            str(index): session.path_flow(index)
            for index in range(1, int(meta["paths"]) + 1)
        }

        payload = {
            "marker": "GENERATED_CONTAM_DYNAMIC_CONTROL_EXECUTED",
            "prj": args.prj,
            "zones": meta["zones"],
            "paths": meta["paths"],
            "time_step_s": meta["time_step_s"],
            "version": meta["version"],
            "input_controls": meta["input_controls"],
            "input_control_names": meta["input_control_names"],
            "w1_input_control_index": w1_index,
            "w1_open_path_flow_kg_s": open_flows["1"],
            "w1_closed_path_flow_kg_s": closed_flows["1"],
            "open_path_flow_kg_s": open_flows,
            "closed_path_flow_kg_s": closed_flows,
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
        if not any(abs(value) > 1e-12 for value in open_flows.values()):
            raise RuntimeError("generated CONTAM project produced zero flow on every path")
        open_w1 = abs(open_flows["1"])
        closed_w1 = abs(closed_flows["1"])
        if open_w1 <= 1e-12:
            raise RuntimeError("W1 open control produced no measurable path flow")
        if closed_w1 > max(1e-8, open_w1 * 0.10):
            raise RuntimeError(
                f"W1 close control did not suppress path flow: open={open_w1}, closed={closed_w1}"
            )
        return 0
    finally:
        if session.started:
            session.close()


if __name__ == "__main__":
    raise SystemExit(main())
