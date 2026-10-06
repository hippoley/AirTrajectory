"""Capture and validate WindowPilot field data in one command."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.demo_physical_config import (
    build_windowpilot_drivers,
    load_windowpilot_driver_config,
)
from airtrajectory.layout import LayoutContract
from airtrajectory.windowpilot_validation_pipeline import (
    run_windowpilot_field_validation,
)
from airtrajectory.windowpilot_contract_probe import (
    probe_windowpilot_config,
)
from airtrajectory.windowpilot_contract_baseline import (
    compare_windowpilot_contract_baseline,
)


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("runtime_receipt", type=Path)
    parser.add_argument("protocol", type=Path)
    parser.add_argument("windowpilot_config", type=Path)
    parser.add_argument("--validation-id", required=True)
    parser.add_argument(
        "--layout",
        type=Path,
        default=Path("web/data/home_topology.fixed.json"),
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--capture-out", type=Path)
    parser.add_argument("--aligned-out", type=Path)
    parser.add_argument("--contract-baseline", type=Path)
    parser.add_argument("--probe-out", type=Path)
    parser.add_argument("--contract-check-out", type=Path)
    parser.add_argument("--require-pass", action="store_true")
    args = parser.parse_args()

    config = load_windowpilot_driver_config(args.windowpilot_config)

    baseline = None
    probe_report = None
    if args.contract_baseline is not None:
        baseline = _load(args.contract_baseline)
        probe_report = probe_windowpilot_config(config=config)
        comparison = compare_windowpilot_contract_baseline(
            baseline=baseline,
            current_report=probe_report,
        )

        if args.probe_out is not None:
            args.probe_out.parent.mkdir(parents=True, exist_ok=True)
            args.probe_out.write_text(
                json.dumps(probe_report, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        if args.contract_check_out is not None:
            args.contract_check_out.parent.mkdir(parents=True, exist_ok=True)
            args.contract_check_out.write_text(
                json.dumps(comparison, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

        if comparison["status"] != "MATCH":
            print(json.dumps(comparison, indent=2, sort_keys=True))
            return 3

    receipt, capture, aligned = run_windowpilot_field_validation(
        layout=LayoutContract.from_file(args.layout),
        config=config,
        drivers=build_windowpilot_drivers(config),
        protocol=_load(args.protocol),
        runtime_receipt=_load(args.runtime_receipt),
        validation_id=args.validation_id,
        contract_baseline=baseline,
        contract_probe_report=probe_report,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.capture_out is not None:
        args.capture_out.parent.mkdir(parents=True, exist_ok=True)
        args.capture_out.write_text(
            json.dumps(capture, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if args.aligned_out is not None:
        args.aligned_out.parent.mkdir(parents=True, exist_ok=True)
        args.aligned_out.write_text(
            json.dumps(aligned, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    print(json.dumps(receipt, indent=2, sort_keys=True))
    if args.require_pass and not receipt["field_validation_verified"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
