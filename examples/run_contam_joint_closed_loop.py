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
from airtrajectory.physical_origin import verify_physical_origin_receipt
from airtrajectory.spatialruntime_consumer import (
    verify_branch_result_with_spatialruntime,
    verify_generated_prj_with_spatialruntime,
)


ROOT = Path(__file__).resolve().parents[1]


def _sha256(payload):
    import hashlib
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _project_origin_for_contam(profile, origin):
    """Project controller state onto the exact state surface consumed by CONTAM.

    Controller-only scalar state (for example measured rain) remains part of
    the controller/physical-origin lineage, but is not silently passed to a
    CONTAM profile that has no corresponding scalar control.
    """
    controller_scalars=dict(origin.get("scalar_values") or {})
    supported=set(profile.scalar_controls)
    missing=sorted(supported-set(controller_scalars))
    if missing:
        raise RuntimeError(
            "controller origin is missing CONTAM scalar controls: "
            + ",".join(missing)
        )
    contam_scalars={
        key:float(controller_scalars[key])
        for key in sorted(supported)
    }
    dropped={
        key:float(value)
        for key,value in sorted(controller_scalars.items())
        if key not in supported
    }
    projected={
        "co2_ppm":dict(origin["co2_ppm"]),
        "opening_pct":dict(origin["opening_pct"]),
        "scalar_values":contam_scalars,
    }
    evidence={
        "controller_scalar_values":{
            key:float(value)
            for key,value in sorted(controller_scalars.items())
        },
        "contam_scalar_values":dict(contam_scalars),
        "dropped_scalar_values":dropped,
        "scalar_projection_applied":bool(dropped),
        "evidence_boundary":(
            "controller-only scalar state remains in physical/controller origin "
            "lineage; CONTAM receives only scalar controls explicitly configured "
            "by the active ContamForkProfile"
        ),
    }
    return projected,evidence


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
    parser.add_argument(
        "--physical-origin-receipt",
        type=Path,
        help=(
            "Verified physical-origin receipt from WindowPilot field handoff. "
            "When supplied, control_steps must be 1 so only the first plan is "
            "claimed as replanning from measured field state."
        ),
    )
    parser.add_argument("--prediction-horizon-steps", type=int, default=3)
    parser.add_argument(
        "--candidate-mode",
        choices=("adaptive", "independent-only"),
        default="adaptive",
        help="adaptive searches Independent + Joint candidates; independent-only replans only the rule baseline",
    )
    parser.add_argument(
        "--spatialruntime-verify",
        action="store_true",
        help=(
            "verify the generated PRJ and every real ContamX candidate branch "
            "through SpatialRuntime normalization without changing controller selection"
        ),
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
    initial_scalars = {}
    physical_origin_evidence = None
    if args.physical_origin_receipt is not None:
        if args.control_steps != 1:
            raise RuntimeError(
                "physical-origin replanning must use --control-steps 1; "
                "additional steps would be simulation continuation without new field feedback"
            )
        raw_physical_origin = _load(args.physical_origin_receipt)
        physical_origin_evidence = verify_physical_origin_receipt(
            raw_physical_origin
        )
        physical_origin = physical_origin_evidence["origin"]
        missing_zones = sorted(
            set(topology.zones) - set(physical_origin["co2_ppm"])
        )
        missing_openings = sorted(
            set(topology.openings) - set(physical_origin["opening_pct"])
        )
        extra_zones = sorted(
            set(physical_origin["co2_ppm"]) - set(topology.zones)
        )
        extra_openings = sorted(
            set(physical_origin["opening_pct"]) - set(topology.openings)
        )
        if missing_zones or missing_openings or extra_zones or extra_openings:
            raise RuntimeError(
                "physical origin/topology mismatch: "
                f"missing_zones={missing_zones}, "
                f"missing_openings={missing_openings}, "
                f"extra_zones={extra_zones}, "
                f"extra_openings={extra_openings}"
            )
        initial_co2 = {
            zone: float(physical_origin["co2_ppm"][zone])
            for zone in sorted(topology.zones)
        }
        initial_openings = {
            opening_id: float(physical_origin["opening_pct"][opening_id])
            for opening_id in sorted(topology.openings)
        }
        initial_scalars = {
            key: float(value)
            for key, value in physical_origin["scalar_values"].items()
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

    spatialruntime_consumer = None
    if args.spatialruntime_verify:
        spatialruntime_consumer = verify_generated_prj_with_spatialruntime(
            project_path=args.prj,
            provenance=provenance,
            case_id=profile.profile_id,
        )
        if spatialruntime_consumer.get("verified") is not True:
            raise RuntimeError("SpatialRuntime PRJ verification did not pass")

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
        contam_origin, scalar_projection = _project_origin_for_contam(
            profile,
            origin,
        )
        response = contam_strategy_fork_request(
            {
                "profile_id": profile.profile_id,
                "topology_id": layout.topology_id,
                "origin": contam_origin,
                "candidates": list(candidates),
                "horizon_steps": int(horizon),
                "evaluation_zone": "living",
            },
            {profile.profile_id: profile},
        )
        if response.get("origin_kind") != "prj-reseed-verified":
            raise RuntimeError("closed-loop evaluation did not use verified PRJ reseed origin")

        spatialruntime_result_consumers = []
        if args.spatialruntime_verify:
            for branch_index, branch in enumerate(response["branches"]):
                result_receipt = verify_branch_result_with_spatialruntime(
                    project_path=args.prj,
                    provenance=provenance,
                    case_id=profile.profile_id,
                    branch=branch,
                    source_step=step_index,
                    source_revision=branch_index,
                )
                if result_receipt.get("verified") is not True:
                    raise RuntimeError(
                        "SpatialRuntime closed-loop branch verification did not pass"
                    )
                spatialruntime_result_consumers.append(result_receipt)

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
                "controller_origin_sha256": _sha256(origin),
                "contam_origin_sha256": _sha256(contam_origin),
                "scalar_projection": scalar_projection,
                "candidate_scores": sorted(
                    scored,
                    key=lambda row: (row["objective_score"], row["label"]),
                ),
                "spatialruntime_result_consumers": spatialruntime_result_consumers,
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
            scalar_values=initial_scalars,
        ),
        control_steps=args.control_steps,
        prediction_horizon_steps=args.prediction_horizon_steps,
        candidate_provider=candidate_provider,
        evaluator=evaluator,
        executor=executor,
        capability=contam_receding_horizon_capability(profile),
    )
    expected_replanning = args.control_steps > 1
    if receipt["closed_loop_replanning_executed"] is not expected_replanning:
        raise RuntimeError(
            "closed-loop replanning flag does not match control-step count: "
            f"expected={expected_replanning}, "
            f"actual={receipt['closed_loop_replanning_executed']}"
        )
    if len(receipt["steps"]) != args.control_steps:
        raise RuntimeError("closed-loop Joint control-step count mismatch")
    if not all(
        step["evaluation_evidence"].get("origin_kind") == "prj-reseed-verified"
        for step in receipt["steps"]
    ):
        raise RuntimeError("one or more closed-loop steps lacked verified reseed provenance")

    payload = {
        "marker": (
            "REAL_CONTAM_REPLAN_FROM_PHYSICAL_ORIGIN"
            if physical_origin_evidence is not None
            else "REAL_CONTAM_RECEDING_HORIZON_JOINT_EXECUTED"
        ),
        "candidate_mode": args.candidate_mode,
        "physics_fidelity": "CONTAM",
        "evidence_level": profile.evidence_level,
        "engineering_truth": False,
        "field_validated": False,
        "full_restart_verified": False,
        "physical_origin_consumed": physical_origin_evidence is not None,
        "physical_origin_evidence": physical_origin_evidence,
        "spatialruntime_consumer": spatialruntime_consumer,
        "evidence_boundary": (
            "one real-ContamX planning step starts from a verified physical-origin "
            "receipt; no second physical action or second field observation is claimed"
            if physical_origin_evidence is not None
            else "simulation closed loop using verified PRJ Section 15 contaminant reseeding"
        ),
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
