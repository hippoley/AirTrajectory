"""Capture and audit a physical trajectory through a configured WindowPilot runtime."""
import argparse
import json
import hashlib
from pathlib import Path

from airtrajectory.drivers import WindowPilotHTTPDriver
from airtrajectory.physical import (
    PhysicalWindowEnvironment, RulePolicy, SafetyResolver,
    record_physical_trajectory, validate_physical_tau0,
)
from airtrajectory.trajectory import TrajectoryStore


def capture_physical_tau0(*, driver, opening_id, topology_id, steps, out, receipt, commission_bundle=None):
    if commission_bundle is None:
        raise RuntimeError("commissioning evidence bundle is required before physical tau0 capture")
    bundle_path=Path(commission_bundle)
    bundle=json.loads(bundle_path.read_text(encoding="utf-8"))
    if bundle.get("status")!="PASS":
        raise RuntimeError("commissioning evidence bundle did not pass")
    expected=(bundle.get("hardware_identity") or {}).get("identity_sha256")
    if not expected:
        raise RuntimeError("commissioning evidence bundle missing hardware identity")
    readiness=driver.physical_readiness()
    if readiness.get("capture_preconditions") is not True:
        reasons="; ".join(readiness.get("reasons") or [])
        raise RuntimeError("WindowPilot physical capture preconditions not met: "+reasons)
    current=(readiness.get("hardware_identity") or {}).get("identity_sha256")
    if not current or current!=expected:
        raise RuntimeError("commissioned hardware identity does not match current WindowPilot runtime")

    caps=driver.capabilities()
    if caps.simulated:
        raise RuntimeError("WindowPilot execution is still simulated; physical capture aborted")
    if not caps.measured_position:
        raise RuntimeError("WindowPilot has no measured position feedback; physical capture aborted")

    commission_bundle_sha256=hashlib.sha256(bundle_path.read_bytes()).hexdigest()
    env=PhysicalWindowEnvironment(driver,opening_id,require_measured_feedback=True)
    trajectory=record_physical_trajectory(
        env,RulePolicy(opening_id),SafetyResolver(),
        topology_id,TrajectoryStore(out),steps=steps,
        context_extra={
            "commissioning_identity_sha256":expected,
            "runtime_hardware_identity":readiness.get("hardware_identity"),
            "commissioning_bundle_sha256":commission_bundle_sha256,
        },
    )
    report=validate_physical_tau0(trajectory)
    payload={
        "trajectory_id":trajectory.id,
        "valid_tau0":report.valid_tau0,
        "reasons":list(report.reasons),
        "environment_kind":trajectory.environment_kind,
        "steps":len(trajectory.steps),
        "output":str(out),
        "commissioning_identity_sha256":expected,
        "runtime_hardware_identity":readiness.get("hardware_identity"),
        "commissioning_bundle_sha256":commission_bundle_sha256,
        "trajectory_sha256":hashlib.sha256(Path(out).read_bytes()).hexdigest(),
    }
    receipt_path=Path(receipt); receipt_path.parent.mkdir(parents=True,exist_ok=True)
    receipt_path.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    if not report.valid_tau0:
        raise RuntimeError("physical trajectory failed tau0 audit: "+"; ".join(report.reasons))
    return payload


def main(argv=None):
    parser=argparse.ArgumentParser(description="Capture one audited physical AirTrajectory trajectory")
    parser.add_argument("--windowpilot",default="http://127.0.0.1:8000")
    parser.add_argument("--opening-id",default="w1")
    parser.add_argument("--topology-id",default="physical-single-window")
    parser.add_argument("--steps",type=int,default=1)
    parser.add_argument("--out",default="artifacts/physical-tau0.jsonl")
    parser.add_argument("--receipt",default="artifacts/physical-tau0-audit.json")
    parser.add_argument("--commission-bundle",required=True,help="WindowPilot physical bring-up evidence bundle")
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
    )
    print(json.dumps(receipt,ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
