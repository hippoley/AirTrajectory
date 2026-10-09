"""Generate the fixed three-room demo CONTAM PRJ from one topology source.

This command is for software integration / topology-load verification. The bundled
profiles are illustrative and therefore the emitted project is NOT engineering
truth until replaced by validated project-specific profiles.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.contam_allocator import allocate_contam_ids
from airtrajectory.contam_boundary import bind_boundary_profile
from airtrajectory.contam_ir import compile_contam_ir
from airtrajectory.contam_engineering_readiness import audit_engineering_readiness
from airtrajectory.contam_metric_overlay import apply_metric_geometry_overlay
from airtrajectory.contam_prj_profile import bind_prj_serialization_profile
from airtrajectory.contam_prj_readiness import audit_prj_readiness
from airtrajectory.contam_prj_serializer import write_minimal_prj
from airtrajectory.contam_profile import (
    bind_airflow_elements,
    illustrative_opening_profile,
)
from airtrajectory.demo_runtime import DemoRuntimeSnapshot
from airtrajectory.layout import LayoutContract


ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--layout",
        type=Path,
        default=ROOT / "web" / "data" / "home_topology.fixed.json",
    )
    parser.add_argument(
        "--metric-profile",
        type=Path,
        default=ROOT / "examples" / "contam_metric_geometry.example.json",
    )
    parser.add_argument(
        "--boundary-profile",
        type=Path,
        default=ROOT / "examples" / "contam_boundary_profile.example.json",
    )
    parser.add_argument(
        "--prj-profile",
        type=Path,
        default=ROOT / "examples" / "contam_prj_profile.example.json",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "artifacts" / "multispace-generated.prj",
    )
    parser.add_argument("--provenance-out", type=Path)
    parser.add_argument("--airflow-profile", type=Path, help="Explicit airflow profile; required for imported layouts")
    args = parser.parse_args()

    base_layout = LayoutContract.from_file(args.layout)
    if base_layout.source_kind == "imported-floorplan":
        missing = [name for name, value in (
            ("--metric-profile", args.metric_profile),
            ("--boundary-profile", args.boundary_profile),
            ("--prj-profile", args.prj_profile),
            ("--airflow-profile", args.airflow_profile),
        ) if value is None or (name != "--airflow-profile" and value == parser.get_default(name.removeprefix("--").replace("-", "_")))]
        if missing:
            parser.error("imported layouts require explicitly supplied, topology-matched profiles: " + ", ".join(missing))
    runtime = DemoRuntimeSnapshot.resolve(base_layout)

    metric_layout, metric_meta = apply_metric_geometry_overlay(
        base_layout,
        _load(args.metric_profile),
    )
    ir = compile_contam_ir(
        metric_layout,
        opening_positions=runtime.opening_positions,
    )
    manifest = allocate_contam_ids(ir)
    manifest = bind_airflow_elements(
        manifest,
        _load(args.airflow_profile) if args.airflow_profile else illustrative_opening_profile(),
    )
    boundary = _load(args.boundary_profile)
    manifest = bind_boundary_profile(manifest, boundary)
    manifest = bind_prj_serialization_profile(
        manifest,
        _load(args.prj_profile),
    )
    manifest["demo_runtime_snapshot_sha256"] = runtime.sha256()
    manifest["metric_geometry_provenance"] = metric_meta

    readiness = audit_prj_readiness(manifest)
    if not readiness["prj_serialization_ready"]:
        raise RuntimeError(
            "generated manifest unexpectedly failed PRJ readiness: "
            + json.dumps(readiness["missing"], sort_keys=True)
        )

    receipt = write_minimal_prj(manifest, args.out)
    provenance = {
        **receipt,
        "topology_id": base_layout.topology_id,
        "layout_contract_sha256": base_layout.sha256(),
        "source_provenance": base_layout.source_provenance,
        "demo_runtime_snapshot_sha256": runtime.sha256(),
        "metric_geometry_provenance": metric_meta,
        "airflow_profile": manifest["airflow_profile"],
        "boundary_profile": manifest["boundary_profile"],
        "prj_serialization_profile": manifest["prj_serialization_profile"],
        "prj_profile_binding_sha256": manifest[
            "prj_profile_binding_sha256"
        ],
        "zone_numbers": manifest["zone_numbers"],
        "path_numbers": manifest["path_numbers"],
        "control_numbers": manifest["control_numbers"],
        "initial_co2_ppm": {key.split(":",1)[1]: float(value) for key,value in manifest["contaminants"][0]["initial_zone_concentration"].items()},
        "contam_ambient": {"temperature_k": float(manifest["weather"]["outdoor_temperature_c"])+273.15, "pressure_pa": float(manifest["weather"]["barometric_pressure_pa"]), "wind_speed_m_s": float(manifest["weather"]["wind_speed_m_s"]), "wind_direction_deg": float(manifest["weather"]["wind_direction_deg"]), "mass_fractions": {"0": float(manifest["contaminants"][0]["outdoor_mass_fraction"])}},
        "input_control_ranges": receipt["input_control_ranges"],
        "initial_input_controls": {
            str(receipt["control_node_numbers"][opening_id]): {
                "opening_id": opening_id,
                "name": receipt["input_control_names"][opening_id],
                "value": (
                    float(receipt["input_control_ranges"][opening_id]["closed_value"])
                    + (
                        float(receipt["input_control_ranges"][opening_id]["open_value"])
                        - float(receipt["input_control_ranges"][opening_id]["closed_value"])
                    )
                    * (float(runtime.opening_states[opening_id]) / 100.0)
                ),
            }
            for opening_id in sorted(receipt["input_control_names"])
        },
        "readiness_sha256": readiness["readiness_sha256"],
        "engineering_truth": False,
        "purpose": "generated topology/load smoke",
    }
    provenance["engineering_readiness"] = audit_engineering_readiness(
        provenance
    )

    provenance_out = args.provenance_out or args.out.with_suffix(
        args.out.suffix + ".json"
    )
    provenance_out.parent.mkdir(parents=True, exist_ok=True)
    provenance_out.write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(provenance, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
