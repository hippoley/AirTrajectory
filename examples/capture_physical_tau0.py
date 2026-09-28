"""Capture and audit a physical trajectory through a configured WindowPilot runtime."""
import argparse
import hashlib
import json
from pathlib import Path

from airtrajectory.drivers import WindowPilotHTTPDriver
from airtrajectory.physical import (
    PhysicalWindowEnvironment, SafetyResolver, Tau0ProbePolicy,
    record_physical_trajectory, validate_physical_tau0,
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
):
    if commission_bundle is None:
        raise RuntimeError("commissioning evidence bundle is required before physical tau0 capture")

    preflight=validate_physical_tau0_preconditions(
        driver=driver,
        commission_bundle=commission_bundle,
        sensor_apply_receipts=sensor_apply_receipts,
    )
    context_extra={key:preflight[key] for key in _CONTEXT_KEYS}

    if steps!=1:
        raise RuntimeError("physical tau0 capture must contain exactly one bounded probe step")

    policy=Tau0ProbePolicy(opening_id)
    context_extra["tau0_capture_policy"]=policy.capture_policy()
    env=PhysicalWindowEnvironment(driver,opening_id,require_measured_feedback=True)
    trajectory=record_physical_trajectory(
        env,policy,SafetyResolver(),
        topology_id,TrajectoryStore(out),steps=steps,
        context_extra=context_extra,
    )

    report=validate_physical_tau0(trajectory)
    payload={
        "trajectory_id":trajectory.id,
        "valid_tau0":report.valid_tau0,
        "reasons":list(report.reasons),
        "environment_kind":trajectory.environment_kind,
        "steps":len(trajectory.steps),
        "output":str(out),
        **context_extra,
        "trajectory_sha256":hashlib.sha256(Path(out).read_bytes()).hexdigest(),
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
        "--sensor-apply-receipt",
        action="append",
        default=[],
        help=(
            "Optional WindowPilot sensor_apply PASS receipt. Supply exactly "
            "two (CO2 + rain) to upgrade source evidence to probe-apply-audited."
        ),
    )
    args=parser.parse_args(argv)

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
    )
    print(json.dumps(receipt,ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
