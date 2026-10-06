"""Runtime verification for an engineering-input CONTAM build.

A successful engineering build proves approved inputs compile into a PRJ.
This verifier proves that exact PRJ and exact runtime snapshot execute through
the real/fake-injected CONTAM backend and shared multi-window trajectory path.

It does not perform prediction-vs-field validation and therefore does not set
engineering_truth=true.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .demo_orchestrator import run_demo
from .demo_runtime import DemoRuntimeSnapshot
from .layout import LayoutContract


def _sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def verify_engineering_contam_runtime(
    *,
    layout: LayoutContract,
    prj_path: str | Path,
    build_receipt: dict[str, Any],
    steps: int = 2,
    binding_factory=None,
) -> dict[str, Any]:
    if build_receipt.get("status") != "ENGINEERING_INPUTS_READY":
        raise ValueError("build receipt is not ENGINEERING_INPUTS_READY")
    if build_receipt.get("engineering_inputs_ready") is not True:
        raise ValueError("engineering inputs are not ready")
    if (
        (build_receipt.get("engineering_readiness") or {}).get(
            "engineering_ready"
        )
        is not True
    ):
        raise ValueError("engineering evidence readiness is not satisfied")
    if build_receipt.get("runtime_verified") is True:
        raise ValueError("build receipt already claims runtime_verified=true")
    if int(steps) < 1:
        raise ValueError("steps must be >=1")

    target = Path(prj_path)
    if not target.exists():
        raise FileNotFoundError(target)
    actual_prj_sha = _file_sha256(target)
    expected_prj_sha = str(build_receipt.get("sha256") or "")
    if actual_prj_sha != expected_prj_sha:
        raise ValueError("PRJ SHA-256 does not match engineering build receipt")

    if build_receipt.get("topology_id") != layout.topology_id:
        raise ValueError("build receipt topology_id does not match layout")
    if build_receipt.get("layout_contract_sha256") != layout.sha256():
        raise ValueError("layout contract SHA-256 drift")

    snapshot = DemoRuntimeSnapshot.resolve(layout)
    if (
        build_receipt.get("demo_runtime_snapshot_sha256")
        != snapshot.sha256()
    ):
        raise ValueError("demo runtime snapshot SHA-256 drift")

    result = run_demo(
        snapshot,
        mode="contam",
        max_steps=int(steps),
        contam_prj_path=target,
        contam_provenance=build_receipt,
        contam_binding_factory=binding_factory,
    )
    trajectory = result.trajectory
    if trajectory.environment_kind != "contam":
        raise RuntimeError("runtime trajectory environment_kind is not contam")
    if trajectory.policy_id != "multi-window-rule-v1":
        raise RuntimeError("runtime trajectory policy identity drift")
    if len(trajectory.steps) != int(steps):
        raise RuntimeError("runtime trajectory step count mismatch")
    if (
        trajectory.context.get("demo_runtime_snapshot_sha256")
        != snapshot.sha256()
    ):
        raise RuntimeError("runtime trajectory snapshot provenance mismatch")

    expected_zones = {room.id for room in layout.rooms}
    expected_openings = {opening.id for opening in layout.openings}
    for index, step in enumerate(trajectory.steps):
        action_ids = {action.opening_id for action in step.executed_actions}
        if action_ids != expected_openings:
            raise RuntimeError(
                f"runtime step {index} opening action coverage mismatch"
            )
        solved = step.next_observation or {}
        if set((solved.get("co2_ppm") or {})) != expected_zones:
            raise RuntimeError(
                f"runtime step {index} solved CO2 zone coverage mismatch"
            )
        if set((solved.get("path_flow_kg_s") or {})) != expected_openings:
            raise RuntimeError(
                f"runtime step {index} path-flow coverage mismatch"
            )

    reset_info = dict(trajectory.context.get("reset_info") or {})
    contam_meta = dict(reset_info.get("contam") or {})
    expected_zone_count = len(build_receipt.get("zone_numbers") or {})
    expected_path_count = len(build_receipt.get("path_numbers") or {})
    if contam_meta.get("zones") != expected_zone_count:
        raise RuntimeError("ContamX zone count does not match build receipt")
    if contam_meta.get("paths") != expected_path_count:
        raise RuntimeError("ContamX path count does not match build receipt")

    trajectory_payload = trajectory.to_dict()
    build_receipt_sha = _sha256(build_receipt)
    trajectory_sha = _sha256(trajectory_payload)
    time_step_s = float(contam_meta.get("time_step_s") or 0.0)
    if time_step_s <= 0:
        raise RuntimeError("ContamX time_step_s must be positive")
    prediction_series = [
        {
            "step": int(step.index),
            "simulation_time_s": float(step.index + 1) * time_step_s,
            "co2_ppm": {
                str(key): float(value)
                for key, value in sorted(
                    (step.next_observation.get("co2_ppm") or {}).items()
                )
            },
            "opening_pct": {
                str(key): float(value)
                for key, value in sorted(
                    (step.next_observation.get("opening_pct") or {}).items()
                )
            },
            "path_flow_kg_s": {
                str(key): float(value)
                for key, value in sorted(
                    (
                        step.next_observation.get("path_flow_kg_s")
                        or {}
                    ).items()
                )
            },
        }
        for step in trajectory.steps
    ]
    receipt_payload = {
        "schema_version": "0.1",
        "verifier": "contam-engineering-runtime-verifier",
        "status": "ENGINEERING_RUNTIME_VERIFIED",
        "topology_id": layout.topology_id,
        "layout_contract_sha256": layout.sha256(),
        "demo_runtime_snapshot_sha256": snapshot.sha256(),
        "prj_sha256": actual_prj_sha,
        "build_receipt_sha256": build_receipt_sha,
        "trajectory_sha256": trajectory_sha,
        "policy_id": trajectory.policy_id,
        "contam_version": contam_meta.get("version"),
        "zone_count": expected_zone_count,
        "path_count": expected_path_count,
        "steps": int(steps),
        "simulation_time_step_s": time_step_s,
        "prediction_time_origin": "post-reset-policy-step",
        "prediction_series": prediction_series,
        "prediction_series_sha256": _sha256(prediction_series),
        "input_control_names": dict(
            build_receipt.get("input_control_names") or {}
        ),
        "input_control_ranges": dict(
            build_receipt.get("input_control_ranges") or {}
        ),
        "warm_start_strategy": reset_info.get("warm_start_strategy"),
        "engineering_inputs_ready": True,
        "runtime_verified": True,
        "engineering_model_verified": True,
        "field_validation_verified": False,
        "engineering_truth": False,
        "evidence_boundary": (
            "Approved engineering inputs and real CONTAM runtime execution are "
            "verified; prediction-vs-field validation is still required before "
            "engineering_truth can be claimed."
        ),
    }
    return {
        **receipt_payload,
        "runtime_receipt_sha256": _sha256(receipt_payload),
    }
