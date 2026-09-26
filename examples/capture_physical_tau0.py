"""Capture and audit a physical trajectory through a configured WindowPilot runtime."""
import argparse
import json
from pathlib import Path

from airtrajectory.drivers import WindowPilotHTTPDriver
from airtrajectory.physical import (
    PhysicalWindowEnvironment, RulePolicy, SafetyResolver,
    record_physical_trajectory, validate_physical_tau0,
)
from airtrajectory.trajectory import TrajectoryStore


def capture_physical_tau0(*, driver, opening_id, topology_id, steps, out, receipt):
    caps=driver.capabilities()
    if caps.simulated:
        raise RuntimeError("WindowPilot execution is still simulated; physical capture aborted")
    if not caps.measured_position:
        raise RuntimeError("WindowPilot has no measured position feedback; physical capture aborted")

    env=PhysicalWindowEnvironment(driver,opening_id,require_measured_feedback=True)
    trajectory=record_physical_trajectory(
        env,RulePolicy(opening_id),SafetyResolver(),
        topology_id,TrajectoryStore(out),steps=steps,
    )
    report=validate_physical_tau0(trajectory)
    payload={
        "trajectory_id":trajectory.id,
        "valid_tau0":report.valid_tau0,
        "reasons":list(report.reasons),
        "environment_kind":trajectory.environment_kind,
        "steps":len(trajectory.steps),
        "output":str(out),
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
    args=parser.parse_args(argv)

    driver=WindowPilotHTTPDriver(args.windowpilot)
    receipt=capture_physical_tau0(
        driver=driver,
        opening_id=args.opening_id,
        topology_id=args.topology_id,
        steps=args.steps,
        out=args.out,
        receipt=args.receipt,
    )
    print(json.dumps(receipt,ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
