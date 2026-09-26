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
    caps=driver.capabilities()
    if caps.simulated:
        raise RuntimeError("WindowPilot execution is still simulated; physical capture aborted")
    if not caps.measured_position:
        raise RuntimeError("WindowPilot has no measured position feedback; physical capture aborted")

    env=PhysicalWindowEnvironment(driver,args.opening_id,require_measured_feedback=True)
    trajectory=record_physical_trajectory(
        env,RulePolicy(args.opening_id),SafetyResolver(),
        args.topology_id,TrajectoryStore(args.out),steps=args.steps,
    )
    report=validate_physical_tau0(trajectory)
    receipt={
        "trajectory_id":trajectory.id,
        "valid_tau0":report.valid_tau0,
        "reasons":list(report.reasons),
        "environment_kind":trajectory.environment_kind,
        "steps":len(trajectory.steps),
        "output":str(args.out),
    }
    receipt_path=Path(args.receipt); receipt_path.parent.mkdir(parents=True,exist_ok=True)
    receipt_path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(receipt,ensure_ascii=False))
    if not report.valid_tau0:
        raise RuntimeError("physical trajectory failed tau0 audit: "+"; ".join(report.reasons))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
