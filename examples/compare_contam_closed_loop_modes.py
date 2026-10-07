"""Compare adaptive and Independent real-ContamX closed-loop receipts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.closed_loop_compare import compare_closed_loop_modes


ROOT = Path(__file__).resolve().parents[1]


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("adaptive", type=Path)
    parser.add_argument("independent", type=Path)
    parser.add_argument(
        "--golden-case",
        type=Path,
        default=ROOT / "examples" / "golden_case.multispace_joint_v1.json",
    )
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    adaptive = load(args.adaptive)
    independent = load(args.independent)
    case = load(args.golden_case)

    if adaptive.get("candidate_mode") != "adaptive":
        raise RuntimeError("adaptive receipt has wrong candidate_mode")
    if independent.get("candidate_mode") != "independent-only":
        raise RuntimeError("independent receipt has wrong candidate_mode")

    comparison = compare_closed_loop_modes(
        adaptive_receipt=adaptive["receipt"],
        independent_receipt=independent["receipt"],
        iaq_reference_ppm=float(case["metrics"]["iaq_reference_ppm"]),
        high_co2_ppm=float(case["metrics"]["high_co2_ppm"]),
        objective_weights=case["objective_weights"],
    )
    payload = {
        "marker": "REAL_CONTAM_CLOSED_LOOP_MODES_COMPARED",
        "physics_fidelity": "CONTAM",
        "control_steps": adaptive["receipt"]["control_steps"],
        "prediction_horizon_steps": adaptive["receipt"]["prediction_horizon_steps"],
        "comparison": comparison,
        "engineering_truth": False,
        "field_validated": False,
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    print(rendered)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
