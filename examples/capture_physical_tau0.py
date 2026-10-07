"""Capture and audit a physical trajectory through a configured WindowPilot runtime."""
import argparse
from dataclasses import asdict
import hashlib
import json
import uuid
from pathlib import Path

from airtrajectory.drivers import WindowPilotHTTPDriver
from airtrajectory.physical import (
    PhysicalWindowEnvironment, SafetyResolver, Tau0ProbePolicy,
    record_physical_trajectory, validate_physical_tau0,
)
from airtrajectory.physical_closeout import (
    build_closeout_evidence,
    trajectory_last_feedback_timestamp,
)
from airtrajectory.physical_handoff import (
    authorize_tau0_from_planner,
    build_physical_handoff_reconcile,
    extract_closed_loop_opening_action,
)
from airtrajectory.physical_terminal_snapshot import (
    capture_post_closeout_snapshot,
)
from airtrajectory.tau0_preflight import validate_physical_tau0_preconditions
from airtrajectory.trajectory import TrajectoryStore


_CONTEXT_KEYS=(
    "commissioning_identity_sha256",
    "commissioning_hardware_identity",
    "runtime_hardware_identity",
    "thingmodel_lineage",
    "site_lineage",
    "commissioning_bundle_sha256",
    "preflight_receipt_sha256",
    "preflight_hardware_identity_sha256",
    "gateway_contract_sha256",
    "commissioning_behavior_witness",
    "commissioning_behavior_sha256",
    "sensor_evidence_origin",
    "runtime_sensor_lineage",
    "sensor_staging_lineage",
    "sensor_evidence_sha256",
    "position_tolerance_pct",
    "baseline_position_feedback",
)


def _safe_closeout(driver, opening_id, *, tolerance_pct, after_timestamp):
    feedback=driver.set_position(opening_id,0.0)
    return build_closeout_evidence(
        feedback,
        target_pct=0.0,
        tolerance_pct=tolerance_pct,
        after_timestamp=after_timestamp,
    )


def capture_physical_tau0(
    *,
    driver,
    opening_id,
    topology_id,
    steps,
    out,
    receipt,
    commission_bundle=None,
    sensor_apply_receipts=None,
    planner_handoff=None,
    predicted_zone_id=None,
):
    if commission_bundle is None:
        raise RuntimeError("commissioning evidence bundle is required before physical tau0 capture")

    preflight=validate_physical_tau0_preconditions(
        driver=driver,
        commission_bundle=commission_bundle,
        sensor_apply_receipts=sensor_apply_receipts,
    )
    context_extra={key:preflight[key] for key in _CONTEXT_KEYS}
    tolerance=float(preflight["position_tolerance_pct"])
    acceptance=preflight["commissioning_behavior_witness"]["acceptance_policy"]
    physical_authorization=None
    if planner_handoff is not None:
        physical_authorization=authorize_tau0_from_planner(
            planner_handoff,
            acceptance_policy=acceptance,
        )
        target=float(physical_authorization["authorized_target_pct"])
        context_extra["planner_handoff"]=dict(planner_handoff)
        context_extra["physical_authorization"]=dict(physical_authorization)
    else:
        target=min(
            5.0,
            float(acceptance["requested_excursion_pct"]),
            float(acceptance["max_first_excursion_pct"]),
        )
    if steps!=1:
        raise RuntimeError("physical tau0 capture must contain exactly one bounded probe step")
    policy=Tau0ProbePolicy(
        opening_id,
        target_pct=target,
        minimum_reality_delta_pct=2.0,
        position_tolerance_pct=tolerance,
    )
    context_extra["tau0_capture_policy"]=policy.capture_policy()

    env=PhysicalWindowEnvironment(driver,opening_id,require_measured_feedback=True)
    trajectory=None
    capture_error=None
    try:
        trajectory=record_physical_trajectory(
            env,policy,SafetyResolver(),
            topology_id,TrajectoryStore(out),steps=steps,
            context_extra=context_extra,
        )
    except Exception as exc:
        capture_error=exc

    probe_command_scope_id=getattr(
        driver,
        "last_command_idempotency_scope_id",
        None,
    )
    if probe_command_scope_id is not None:
        try:
            probe_command_scope_id=str(uuid.UUID(str(probe_command_scope_id)))
        except (ValueError,TypeError,AttributeError) as exc:
            raise RuntimeError(
                "physical tau0 probe command idempotency scope is invalid"
            ) from exc

    last_feedback_ts=(
        trajectory_last_feedback_timestamp(trajectory)
        if trajectory is not None else 0.0
    )
    closeout=None
    closeout_error=None
    try:
        closeout=_safe_closeout(
            driver,
            opening_id,
            tolerance_pct=tolerance,
            after_timestamp=last_feedback_ts,
        )
    except Exception as exc:
        closeout_error=exc

    closeout_command_scope_id=getattr(
        driver,
        "last_command_idempotency_scope_id",
        None,
    )
    if closeout_command_scope_id is not None:
        try:
            closeout_command_scope_id=str(uuid.UUID(
                str(closeout_command_scope_id)
            ))
        except (ValueError,TypeError,AttributeError) as exc:
            if closeout_error is None:
                closeout_error=RuntimeError(
                    "physical tau0 closeout command idempotency scope is invalid"
                )

    if (
        closeout_error is None
        and (probe_command_scope_id is not None or closeout_command_scope_id is not None)
        and probe_command_scope_id!=closeout_command_scope_id
    ):
        closeout_error=RuntimeError(
            "physical tau0 idempotency scope drift between probe and safe closeout"
        )

    if capture_error is not None:
        if closeout_error is not None:
            raise RuntimeError(
                "physical tau0 capture failed and safe closeout also failed: "
                f"capture={capture_error}; closeout={closeout_error}"
            ) from capture_error
        raise capture_error

    if closeout_error is not None:
        raise RuntimeError(
            "physical tau0 safe closeout failed: "+str(closeout_error)
        ) from closeout_error

    terminal_snapshot=None
    if planner_handoff is not None:
        terminal_snapshot=capture_post_closeout_snapshot(
            driver=driver,
            after_timestamp=float(closeout["feedback"]["timestamp"]),
        )

    report=validate_physical_tau0(trajectory)
    physical_reconcile=None
    if planner_handoff is not None:
        physical_reconcile=build_physical_handoff_reconcile(
            planner_handoff=planner_handoff,
            authorization=physical_authorization,
            trajectory_step=asdict(trajectory.steps[0]),
            zone_id=predicted_zone_id,
            closeout=closeout,
            terminal_snapshot=terminal_snapshot,
            expected_command_scope_id=probe_command_scope_id,
        )
    payload={
        "trajectory_id":trajectory.id,
        "valid_tau0":report.valid_tau0,
        "reasons":list(report.reasons),
        "environment_kind":trajectory.environment_kind,
        "steps":len(trajectory.steps),
        "output":str(out),
        **context_extra,
        "closeout":closeout,
        "command_idempotency_scope_id":probe_command_scope_id,
        "closeout_idempotency_scope_id":closeout_command_scope_id,
        "trajectory_sha256":hashlib.sha256(Path(out).read_bytes()).hexdigest(),
        "planner_handoff":planner_handoff,
        "physical_authorization":physical_authorization,
        "physical_reconcile":physical_reconcile,
        "terminal_sensor_snapshot":terminal_snapshot,
        "sim_to_physical_handoff_verified":bool(
            report.valid_tau0 and physical_reconcile is not None
        ),
    }

    receipt_path=Path(receipt)
    receipt_path.parent.mkdir(parents=True,exist_ok=True)
    receipt_path.write_text(
        json.dumps(payload,ensure_ascii=False,indent=2),
        encoding="utf-8",
    )
    if not report.valid_tau0:
        raise RuntimeError(
            "physical trajectory failed tau0 audit: "+"; ".join(report.reasons)
        )
    return payload


def main(argv=None):
    parser=argparse.ArgumentParser(description="Capture one audited physical AirTrajectory trajectory")
    parser.add_argument("--windowpilot",default="http://127.0.0.1:8000")
    parser.add_argument("--opening-id",default="w1")
    parser.add_argument("--topology-id",default="physical-single-window")
    parser.add_argument("--steps",type=int,default=1)
    parser.add_argument("--out",default="artifacts/physical-tau0.jsonl")
    parser.add_argument("--receipt",default="artifacts/physical-tau0-audit.json")
    parser.add_argument(
        "--commission-bundle",
        required=True,
        help="WindowPilot physical bring-up evidence bundle",
    )
    parser.add_argument(
        "--closed-loop-receipt",
        type=Path,
        help="Optional real-ContamX closed-loop JSON receipt to bind into physical tau0",
    )
    parser.add_argument(
        "--closed-loop-step-index",
        type=int,
        default=0,
        help="Closed-loop step whose selected opening action becomes the planner handoff",
    )
    parser.add_argument(
        "--predicted-zone-id",
        help="Optional zone key used to compare simulated predicted CO2 with measured post-action CO2",
    )
    parser.add_argument(
        "--sensor-apply-receipt",
        action="append",
        default=[],
        help=(
            "Optional WindowPilot sensor_apply PASS receipt. Supply exactly "
            "two (CO2 + rain) to upgrade source evidence to probe-apply-audited."
        ),
    )
    args=parser.parse_args(argv)

    planner_handoff=None
    if args.closed_loop_receipt is not None:
        closed_loop_payload=json.loads(
            args.closed_loop_receipt.read_text(encoding="utf-8")
        )
        planner_handoff=extract_closed_loop_opening_action(
            closed_loop_payload,
            step_index=args.closed_loop_step_index,
            opening_id=args.opening_id,
        )

    driver=WindowPilotHTTPDriver(args.windowpilot)
    receipt=capture_physical_tau0(
        driver=driver,
        opening_id=args.opening_id,
        topology_id=args.topology_id,
        steps=args.steps,
        out=args.out,
        receipt=args.receipt,
        commission_bundle=args.commission_bundle,
        sensor_apply_receipts=args.sensor_apply_receipt,
        planner_handoff=planner_handoff,
        predicted_zone_id=args.predicted_zone_id,
    )
    print(json.dumps(receipt,ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
