"""Capture and audit a physical trajectory through a configured WindowPilot runtime."""
import argparse
import hashlib
import json
from pathlib import Path

from airtrajectory.drivers import WindowPilotHTTPDriver
from airtrajectory.lineage import (
    compare_hardware_site_lineage,
    compare_hardware_thingmodel_lineage,
    require_hardware_site_lineage,
    require_hardware_thingmodel_lineage,
)
from airtrajectory.physical import (
    PhysicalWindowEnvironment, RulePolicy, SafetyResolver,
    record_physical_trajectory, validate_physical_tau0,
)
from airtrajectory.trajectory import TrajectoryStore


def _is_sha256(value) -> bool:
    text=str(value or "")
    return len(text)==64 and all(ch in "0123456789abcdefABCDEF" for ch in text)


def capture_physical_tau0(
    *, driver, opening_id, topology_id, steps, out, receipt, commission_bundle=None,
):
    if commission_bundle is None:
        raise RuntimeError("commissioning evidence bundle is required before physical tau0 capture")

    bundle_path=Path(commission_bundle)
    bundle=json.loads(bundle_path.read_text(encoding="utf-8"))
    if bundle.get("status")!="PASS":
        raise RuntimeError("commissioning evidence bundle did not pass")

    commissioning_identity=bundle.get("hardware_identity") or {}
    expected=commissioning_identity.get("identity_sha256")
    if not expected:
        raise RuntimeError("commissioning evidence bundle missing hardware identity")

    preflight=bundle.get("preflight")
    if not isinstance(preflight,dict):
        raise RuntimeError("commissioning evidence bundle missing read-only preflight lineage")
    preflight_receipt_sha256=str(preflight.get("receipt_sha256") or "")
    preflight_identity_sha256=str(preflight.get("hardware_identity_sha256") or "")
    gateway_contract_sha256=str(preflight.get("gateway_contract_sha256") or "")
    for label,value in (
        ("preflight receipt",preflight_receipt_sha256),
        ("gateway contract",gateway_contract_sha256),
    ):
        if not _is_sha256(value):
            raise RuntimeError(f"commissioning evidence bundle has invalid {label} SHA-256")
    if preflight_identity_sha256!=expected:
        raise RuntimeError("preflight hardware identity does not match commissioning hardware identity")

    # Cross-repository evidence contract. AirTrajectory does not embed the
    # vendor registry; it requires the commissioning identity to carry the
    # product/source/registry/contract hashes WindowPilot verified.
    thingmodel_lineage=require_hardware_thingmodel_lineage(
        commissioning_identity,
        label="commissioning hardware identity",
    )
    site_lineage=require_hardware_site_lineage(
        commissioning_identity,
        label="commissioning hardware identity",
    )

    readiness=driver.physical_readiness()
    if readiness.get("capture_preconditions") is not True:
        reasons="; ".join(readiness.get("reasons") or [])
        raise RuntimeError("WindowPilot physical capture preconditions not met: "+reasons)

    runtime_identity=readiness.get("hardware_identity") or {}
    current=runtime_identity.get("identity_sha256")
    if not current or current!=expected:
        raise RuntimeError("commissioned hardware identity does not match current WindowPilot runtime")
    compare_hardware_thingmodel_lineage(
        commissioning_identity,
        runtime_identity,
        label="runtime",
    )
    compare_hardware_site_lineage(
        commissioning_identity,
        runtime_identity,
        label="runtime",
    )

    registry_bound=readiness.get("registry_bound_sensors")
    if registry_bound != {"co2_ppm":True,"rain":True}:
        raise RuntimeError(
            "WindowPilot physical capture requires registry-bound CO2 and rain evidence"
        )
    site_bound=readiness.get("site_bound_sensors")
    if site_bound != {"co2_ppm":True,"rain":True}:
        raise RuntimeError(
            "WindowPilot physical capture requires site-bound CO2 and rain evidence"
        )

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
            "commissioning_hardware_identity":commissioning_identity,
            "runtime_hardware_identity":runtime_identity,
            "thingmodel_lineage":thingmodel_lineage,
            "site_lineage":site_lineage,
            "commissioning_bundle_sha256":commission_bundle_sha256,
            "preflight_receipt_sha256":preflight_receipt_sha256,
            "preflight_hardware_identity_sha256":preflight_identity_sha256,
            "gateway_contract_sha256":gateway_contract_sha256,
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
        "commissioning_hardware_identity":commissioning_identity,
        "runtime_hardware_identity":runtime_identity,
        "thingmodel_lineage":thingmodel_lineage,
        "site_lineage":site_lineage,
        "commissioning_bundle_sha256":commission_bundle_sha256,
        "preflight_receipt_sha256":preflight_receipt_sha256,
        "preflight_hardware_identity_sha256":preflight_identity_sha256,
        "gateway_contract_sha256":gateway_contract_sha256,
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
