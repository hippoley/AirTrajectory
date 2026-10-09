"""One-shot engineering-input build for the fixed-layout CONTAM pipeline.

This compiles approved evidence bundles into engineering profiles, generates the
CONTAM project, and audits input readiness. It deliberately does NOT mark runtime
verification complete; real ContamX execution remains a separate gate.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contam_allocator import allocate_contam_ids
from .contam_boundary import bind_boundary_profile
from .contam_engineering_readiness import audit_engineering_readiness
from .contam_ir import compile_contam_ir
from .contam_metric_overlay import apply_metric_geometry_overlay
from .contam_prj_profile import bind_prj_serialization_profile
from .contam_prj_readiness import audit_prj_readiness
from .contam_prj_serializer import write_minimal_prj
from .contam_profile import bind_airflow_elements
from .contam_profile_compiler import (
    attach_prj_review_evidence,
    compile_airflow_profile_from_evidence,
    compile_boundary_profile_from_evidence,
    compile_metric_overlay_from_evidence,
)
from .demo_runtime import DemoRuntimeSnapshot
from .layout import LayoutContract


def build_engineering_contam_project(
    *,
    layout: LayoutContract,
    metric_evidence: dict[str, Any],
    airflow_evidence: dict[str, Any],
    boundary_evidence: dict[str, Any],
    prj_profile: dict[str, Any],
    prj_review_evidence: dict[str, Any],
    out_path: str | Path,
    approved_control_opening_ids: list[str] | None = None,
) -> dict[str, Any]:
    metric_profile = compile_metric_overlay_from_evidence(
        layout,
        metric_evidence,
    )
    airflow_profile = compile_airflow_profile_from_evidence(
        layout,
        airflow_evidence,
    )
    boundary_profile = compile_boundary_profile_from_evidence(
        layout,
        boundary_evidence,
    )
    reviewed_prj_profile = attach_prj_review_evidence(
        topology_id=layout.topology_id,
        prj_profile=prj_profile,
        review_bundle=prj_review_evidence,
    )

    for name, profile in (
        ("metric", metric_profile),
        ("airflow", airflow_profile),
        ("boundary", boundary_profile),
        ("prj", reviewed_prj_profile),
    ):
        if profile.get("engineering_validated") is not True:
            raise ValueError(
                f"{name} engineering profile is not explicitly approved"
            )

    metric_layout, metric_meta = apply_metric_geometry_overlay(
        layout,
        metric_profile,
    )
    runtime = DemoRuntimeSnapshot.resolve(layout)
    ir = compile_contam_ir(
        metric_layout,
        opening_positions=runtime.opening_positions,
    )
    manifest = allocate_contam_ids(ir)
    manifest = bind_airflow_elements(
        manifest,
        airflow_profile,
        require_engineering_validated=True,
    )
    manifest = bind_boundary_profile(
        manifest,
        boundary_profile,
        require_engineering_validated=True,
    )
    manifest = bind_prj_serialization_profile(
        manifest,
        reviewed_prj_profile,
        require_engineering_validated=True,
    )
    if approved_control_opening_ids is not None:
        manifest["approved_control_opening_ids"] = list(approved_control_opening_ids)
    manifest["demo_runtime_snapshot_sha256"] = runtime.sha256()
    manifest["metric_geometry_provenance"] = metric_meta

    prj_readiness = audit_prj_readiness(manifest)
    if not prj_readiness["prj_serialization_ready"]:
        raise RuntimeError(
            "engineering manifest failed PRJ readiness: "
            + json.dumps(prj_readiness["missing"], sort_keys=True)
        )

    receipt = write_minimal_prj(manifest, out_path)
    provenance = {
        **receipt,
        "topology_id": layout.topology_id,
        "layout_contract_sha256": layout.sha256(),
        "demo_runtime_snapshot_sha256": runtime.sha256(),
        "metric_geometry_provenance": metric_meta,
        "airflow_profile": manifest["airflow_profile"],
        "boundary_profile": manifest["boundary_profile"],
        "prj_serialization_profile": manifest[
            "prj_serialization_profile"
        ],
        "prj_profile_binding_sha256": manifest[
            "prj_profile_binding_sha256"
        ],
        "zone_numbers": manifest["zone_numbers"],
        "path_numbers": manifest["path_numbers"],
        "control_numbers": manifest["control_numbers"],
        "initial_co2_ppm": {
            key.split(":", 1)[1]: float(value)
            for key, value in manifest["contaminants"][0][
                "initial_zone_concentration"
            ].items()
        },
        "contam_ambient": {
            "temperature_k": float(
                manifest["weather"]["outdoor_temperature_c"]
            ) + 273.15,
            "pressure_pa": float(
                manifest["weather"]["barometric_pressure_pa"]
            ),
            "wind_speed_m_s": float(
                manifest["weather"]["wind_speed_m_s"]
            ),
            "wind_direction_deg": float(
                manifest["weather"]["wind_direction_deg"]
            ),
            "mass_fractions": {
                "0": float(
                    manifest["contaminants"][0][
                        "outdoor_mass_fraction"
                    ]
                )
            },
        },
        "input_control_ranges": receipt["input_control_ranges"],
        "input_control_names": receipt["input_control_names"],
        "control_node_numbers": receipt["control_node_numbers"],
        "initial_input_controls": {
            str(receipt["control_node_numbers"][opening_id]): {
                "opening_id": opening_id,
                "name": receipt["input_control_names"][opening_id],
                "value": (
                    float(
                        receipt["input_control_ranges"][opening_id][
                            "closed_value"
                        ]
                    )
                    + (
                        float(
                            receipt["input_control_ranges"][opening_id][
                                "open_value"
                            ]
                        )
                        - float(
                            receipt["input_control_ranges"][opening_id][
                                "closed_value"
                            ]
                        )
                    )
                    * (
                        float(runtime.opening_states[opening_id])
                        / 100.0
                    )
                ),
            }
            for opening_id in sorted(receipt["input_control_names"])
        },
        "readiness_sha256": prj_readiness["readiness_sha256"],
        "runtime_verified": False,
        "engineering_truth": False,
        "purpose": "engineering-input build; runtime verification pending",
    }
    engineering = audit_engineering_readiness(provenance)
    if not engineering["engineering_ready"]:
        raise RuntimeError(
            "engineering evidence audit failed: "
            + json.dumps(engineering["blockers"], sort_keys=True)
        )

    provenance["engineering_readiness"] = engineering
    provenance["engineering_inputs_ready"] = True
    provenance["status"] = "ENGINEERING_INPUTS_READY"
    return provenance


def write_engineering_build_receipt(
    provenance: dict[str, Any],
    path: str | Path,
) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
