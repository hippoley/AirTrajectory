"""Run the fixed Independent-vs-Joint Golden Case on real transient ContamX."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.contam import ContamControl
from airtrajectory.contam_fork import (
    ContamForkProfile,
    contam_strategy_fork_request,
)
from airtrajectory.contam_joint_golden_case import (
    build_strategy_candidates,
    compare_independent_vs_joint,
    normalize_golden_case,
)
from airtrajectory.demo_runtime import DemoRuntimeSnapshot
from airtrajectory.layout import LayoutContract
from airtrajectory.ventilation_path_candidates import (
    inject_ventilation_path_candidates,
)
from airtrajectory.spatialruntime_consumer import (
    verify_generated_prj_with_spatialruntime,
)


ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


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
    parser.add_argument("--out", type=Path)
    parser.add_argument(
        "--spatialruntime-verify",
        action="store_true",
        help="verify generated PRJ identity/bindings through the SpatialRuntime consumer boundary",
    )
    parser.add_argument(
        "--derive-path-candidates",
        action="store_true",
        help="replace manual joint candidates with topology-derived VentilationPath candidates",
    )
    parser.add_argument(
        "--path-intensities",
        default="35,55,75",
        help="comma-separated opening percentages for topology-derived path candidates",
    )
    args = parser.parse_args()

    provenance = _load(args.provenance)
    if provenance.get("contaminant_simulation_mode") != "transient":
        raise RuntimeError("Golden Case requires transient CONTAM mode")

    layout = LayoutContract.from_file(args.layout)
    topology = layout.to_building_topology()
    snapshot = DemoRuntimeSnapshot.resolve(layout)
    raw_case = _load(args.golden_case)
    candidate_source = "manual-golden-case"
    path_candidate_metadata = []
    if args.derive_path_candidates:
        try:
            intensities = tuple(
                float(item.strip())
                for item in args.path_intensities.split(",")
                if item.strip()
            )
        except ValueError as exc:
            raise RuntimeError("--path-intensities must be numeric") from exc
        raw_case = inject_ventilation_path_candidates(
            raw_case,
            topology,
            intensities=intensities,
        )
        candidate_source = raw_case["candidate_source"]
        path_candidate_metadata = list(raw_case["ventilation_path_candidates"])
    if str(raw_case.get("topology_id") or "") != layout.topology_id:
        raise RuntimeError("Golden Case topology_id does not match layout")
    case = normalize_golden_case(raw_case, topology)

    if int(provenance.get("time_step_s") or 0) != case["time_step_s"]:
        raise RuntimeError("Golden Case time_step_s does not match generated PRJ")

    initial_co2 = {
        key: float(value)
        for key, value in provenance["initial_co2_ppm"].items()
    }
    if initial_co2 != case["origin"]["co2_ppm"]:
        raise RuntimeError(
            "Golden Case origin CO2 does not match generated PRJ provenance"
        )

    origin_openings = {
        opening_id: float(snapshot.opening_states[opening_id])
        for opening_id in topology.openings
    }
    if origin_openings != case["origin"]["opening_pct"]:
        raise RuntimeError(
            "Golden Case opening origin does not match DemoRuntimeSnapshot"
        )

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
    for opening_id, name in (
        provenance.get("input_control_names") or {}
    ).items():
        bounds = (
            provenance.get("input_control_ranges") or {}
        ).get(opening_id) or {}
        controls[opening_id] = ContamControl(
            control_name=name,
            closed_value=float(bounds.get("closed_value", 0.0)),
            open_value=float(bounds.get("open_value", 1.0)),
        )

    fixed = {
        opening_id: float(origin_openings[opening_id])
        for opening_id in topology.openings
        if opening_id not in controls
    }
    profile = ContamForkProfile(
        case["golden_case_id"],
        topology,
        args.prj,
        zone_numbers,
        controls,
        path_numbers=path_numbers,
        fixed_openings=fixed,
        ambient=dict(provenance.get("contam_ambient") or {}),
        initial_input_controls={
            int(index): dict(spec)
            for index, spec in (
                provenance.get("initial_input_controls") or {}
            ).items()
        },
        evaluation_zone="living",
        evidence_level="real-contam-transient-golden-demo",
        trusted_for_promotion=False,
        prj_initial_co2_ppm=initial_co2,
        origin_state_mode="prj-initial-only",
    )

    candidates = build_strategy_candidates(case, topology)
    response = contam_strategy_fork_request(
        {
            "profile_id": case["golden_case_id"],
            "topology_id": case["topology_id"],
            "origin": {
                "co2_ppm": initial_co2,
                "opening_pct": origin_openings,
                "scalar_values": {},
            },
            "candidates": candidates,
            "horizon_steps": case["horizon_steps"],
            "evaluation_zone": "living",
        },
        {case["golden_case_id"]: profile},
    )

    if response.get("origin_opening_controls_applied") is not True:
        raise RuntimeError("Golden Case origin opening controls were not applied")
    if len(response.get("branches") or []) != len(candidates):
        raise RuntimeError("Golden Case branch count mismatch")
    for branch in response["branches"]:
        series = branch.get("co2_series_by_zone") or {}
        if set(series) != set(topology.zones):
            raise RuntimeError(
                f"Golden Case branch {branch.get('label')} lacks complete zone series"
            )
        if any(len(values) != case["horizon_steps"] for values in series.values()):
            raise RuntimeError(
                f"Golden Case branch {branch.get('label')} horizon mismatch"
            )

    receipt = compare_independent_vs_joint(
        response=response,
        case=case,
        topology=topology,
        prj_sha256=provenance.get("sha256"),
    )
    spatialruntime_receipt = None
    if args.spatialruntime_verify:
        spatialruntime_receipt = verify_generated_prj_with_spatialruntime(
            project_path=args.prj,
            provenance=provenance,
            case_id=case["golden_case_id"],
        )
        if spatialruntime_receipt.get("verified") is not True:
            raise RuntimeError("SpatialRuntime consumer verification did not pass")
    if receipt["non_regression"] is not True:
        raise RuntimeError("Joint search regressed below included independent reference")

    payload = {
        "marker": "REAL_CONTAM_JOINT_GOLDEN_CASE_EXECUTED",
        "engine_version": (response.get("contam") or {}).get("version"),
        "physics_fidelity": response.get("physics_fidelity"),
        "evidence_level": response.get("evidence_level"),
        "trusted_for_promotion": response.get("trusted_for_promotion"),
        "golden_case": case,
        "candidate_source": candidate_source,
        "ventilation_path_candidates": path_candidate_metadata,
        "comparison": receipt,
        "spatialruntime_consumer": spatialruntime_receipt,
        "branches": response["branches"],
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    print(rendered)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
