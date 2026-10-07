"""Run a two-step real-ContamX receding-horizon Joint smoke.

This is a simulation closed loop:
- plan from current solved state with real transient ContamX
- select the best candidate by the existing whole-home objective
- execute only the first solved step of that selected rollout
- re-seed Section 15 from that solved CO2 state
- re-plan from the new origin

It is not field feedback and does not claim native CONTAM restart/time continuity.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from airtrajectory.contam import ContamControl
from airtrajectory.contam_fork import ContamForkProfile, contam_strategy_fork_request
from airtrajectory.contam_joint_golden_case import (
    build_strategy_candidates,
    normalize_golden_case,
    score_strategy_branch,
)
from airtrajectory.demo_runtime import DemoRuntimeSnapshot
from airtrajectory.joint_closed_loop import (
    ClosedLoopOrigin,
    contam_receding_horizon_capability,
    run_receding_horizon_joint,
)
from airtrajectory.layout import LayoutContract


ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _case_for_origin(base_case, origin, topology):
    raw = copy.deepcopy(dict(base_case))
    raw.pop("golden_case_sha256", None)
    raw["origin"] = {
        "co2_ppm": {
            zone: float(origin["co2_ppm"][zone])
            for zone in sorted(topology.zones)
        },
        "opening_pct": {
            opening_id: float(origin["opening_pct"][opening_id])
            for opening_id in sorted(topology.openings)
        },
    }
    return normalize_golden_case(raw, topology)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prj", type=Path)
    parser.add_argument("provenance", type=Path)
    parser.add_argument(
        "--golden-case",
        type=Path,
        default=ROOT / "examples" / "golden_case.multispace_joint_v1.json",
    )
    parser.add_argument(
        "--layout",
        type=Path,
        default=ROOT / "web" / "data" / "home_topology.fixed.json",
    )
    parser.add_argument("--control-steps", type=int, default=2)
    parser.add_argument("--prediction-horizon-steps", type=int, default=3)
    parser.add_argument(
        "--candidate-mode",
        choices=("adaptive", "independent-only"),
        default="adaptive",
        help="adaptive searches Independent + Joint candidates; independent-only replans only the rule baseline",
    )
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    provenance = _load(args.provenance)
    if provenance.get("contaminant_simulation_mode") != "transient":
        raise RuntimeError("closed-loop Joint smoke requires transient CONTAM mode")

    layout = LayoutContract.from_file(args.layout)
    topology = layout.to_building_topology()
    snapshot = DemoRuntimeSnapshot.resolve(layout)
    base_case = normalize_golden_case(_load(args.golden_case), topology)

    zone_numbers = {
        key.split(":", 1)[1]: int(value)
        for key, value in provenance["zone_numbers"].items()
        if key.startswith("zone:")
    }
    path_numbers = {
        key.split(":", 1)[1]: int(value)
        for key, value in provenance["path_numbers"].items()
        if key.startswith("path:")
    }
    controls = {}
    for opening_id, name in (provenance.get("input_control_names") or {}).items():
        bounds = (provenance.get("input_control_ranges") or {}).get(opening_id) or {}
        controls[opening_id] = ContamControl(
            control_name=name,
            closed_value=float(bounds.get("closed_value", 0.0)),
            open_value=float(bounds.get("open_value", 1.0)),
        )

    initial_openings = {
        opening_id: float(snapshot.opening_states[opening_id])
        for opening_id in topology.openings
    }
    initial_co2 = {
        key: float(value)
        for key, value in provenance["initial_co2_ppm"].items()
    }
    fixed = {
        opening_id: float(initial_openings[opening_id])
        for opening_id in topology.openings
        if opening_id not in controls
    }

    profile = ContamForkProfile(
        "closed-loop-joint-real-contam-v1",
        topology,
        args.prj,
        zone_numbers,
        controls,
        path_numbers=path_numbers,
        fixed_openings=fixed,
        ambient=dict(provenance.get("contam_ambient") or {}),
        initial_input_controls={
            int(index): dict(spec)
            for index, spec in (provenance.get("initial_input_controls") or {}).items()
        },
        evaluation_zone="living",
        evidence_level="real-contam-transient-receding-horizon-demo",
        trusted_for_promotion=False,
        prj_initial_co2_ppm=initial_co2,
        origin_state_mode="prj-initial-only",
        prj_reseed_continuation_verified=True,
    )

    selected_branch_by_step = {}
    step_cases = {}

    def candidate_provider(origin, step_index):
        step_case = _case_for_origin(base_case, origin, topology)
        step_cases[step_index] = step_case
        candidates = build_strategy_candidates(step_case, topology)
        if args.candidate_mode == "independent-only":
            candidates = [
                candidate
                for candidate in candidates
                if candidate["label"] == "independent-reference"
            ]
        if not candidates:
            raise RuntimeError("closed-loop candidate set is empty")
        return candidates

    def evaluator(origin, candidates, horizon, step_index):
        step_case = step_cases[step_index]
        response = contam_strategy_fork_request(
            {
                "profile_id": profile.profile_id,
                "topology_id": layout.topology_id,
                "origin": origin,
                "candidates": list(candidates),
                "horizon_steps": int(horizon),
                "evaluation_zone": "living",
            },
            {profile.profile_id: profile},
        )
        if response.get("origin_kind") != "prj-reseed-verified":
            raise RuntimeError("closed-loop evaluation did not use verified PRJ reseed origin")
        scored = [
            score_strategy_branch(branch, case=step_case, topology=topology)
            for branch in response["branches"]
        ]
        selected_score = min(
            scored,
            key=lambda row: (row["objective_score"], row["label"]),
        )
        selected_branch = next(
            branch
            for branch in response["branches"]
            if branch["label"] == selected_score["label"]
        )
        selected_branch_by_step[step_index] = selected_branch
        return {
            "selected_label": selected_score["label"],
            "selected_actions": selected_branch["actions"],
            "objective_score": selected_score["objective_score"],
            "evidence": {
                "physics_fidelity": response["physics_fidelity"],
                "origin_kind": response["origin_kind"],
                "prj_reseed_continuation_verified": response[
                    "prj_reseed_continuation_verified"
                ],
                "prj_reseed_receipt": response["prj_reseed_receipt"],
                "candidate_scores": sorted(
                    scored,
                    key=lambda row: (row["objective_score"], row["label"]),
                ),
            },
        }

    def executor(origin, actions, step_index):
        branch = selected_branch_by_step[step_index]
        zone_series = branch["co2_series_by_zone"]
        opening_series = branch["opening_pct_series"]
        if not opening_series:
            raise RuntimeError("selected branch contains no opening state series")
        return {
            "co2_ppm": {
                zone: float(zone_series[zone][0])
                for zone in sorted(topology.zones)
            },
            "opening_pct": {
                opening_id: float(opening_series[0][opening_id])
                for opening_id in sorted(topology.openings)
            },
            "scalar_values": {},
            "path_flow_kg_s": dict(branch.get("path_flow_kg_s") or {}),
            "state_source": "selected-real-contam-rollout-first-step",
            "physics_fidelity": "CONTAM",
        }

    receipt = run_receding_horizon_joint(
        initial_origin=ClosedLoopOrigin(
            co2_ppm=initial_co2,
            opening_pct=initial_openings,
        ),
        control_steps=args.control_steps,
        prediction_horizon_steps=args.prediction_horizon_steps,
        candidate_provider=candidate_provider,
        evaluator=evaluator,
        executor=executor,
        capability=contam_receding_horizon_capability(profile),
    )
    if receipt["closed_loop_replanning_executed"] is not True:
        raise RuntimeError("closed-loop Joint receipt did not execute replanning")
    if len(receipt["steps"]) != args.control_steps:
        raise RuntimeError("closed-loop Joint control-step count mismatch")
    if not all(
        step["evaluation_evidence"].get("origin_kind") == "prj-reseed-verified"
        for step in receipt["steps"]
    ):
        raise RuntimeError("one or more closed-loop steps lacked verified reseed provenance")

    payload = {
        "marker": "REAL_CONTAM_RECEDING_HORIZON_JOINT_EXECUTED",
        "candidate_mode": args.candidate_mode,
        "physics_fidelity": "CONTAM",
        "evidence_level": profile.evidence_level,
        "engineering_truth": False,
        "field_validated": False,
        "full_restart_verified": False,
        "receipt": receipt,
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    print(rendered)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
