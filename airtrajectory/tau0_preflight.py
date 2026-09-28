"""Read-only preflight for audited physical tau0 capture.

This module is the single owner of the cross-repository gate between a PASS
WindowPilot commissioning bundle and AirTrajectory physical capture.  It
performs no actuator motion.

PASS means:
- WindowPilot commissioning behavior evidence is canonical and reversible;
- the commissioning, preflight and live runtime hardware identities agree;
- ThingModel and physical-site lineage agree end-to-end;
- WindowPilot declares both capture_preconditions and physical_write_ready;
- live CO2 and rain evidence is fresh, measured, registry-bound and site-bound;
- optional sensor_apply receipts, when supplied, validate against the same
  commissioning/runtime/site lineage;
- the runtime is non-simulated and advertises measured position feedback.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from .commissioning import require_commissioning_behavior
from .lineage import (
    compare_hardware_site_lineage,
    compare_hardware_thingmodel_lineage,
    is_sha256,
    require_hardware_site_lineage,
    require_hardware_thingmodel_lineage,
)
from .sensor_lineage import build_sensor_evidence


def _load_bundle(path: Path) -> dict:
    if not path.exists():
        raise RuntimeError(f"commissioning evidence bundle does not exist: {path}")
    try:
        payload=json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"commissioning evidence bundle is not valid JSON: {path}") from exc
    if not isinstance(payload,dict):
        raise RuntimeError("commissioning evidence bundle must be a JSON object")
    return payload


def validate_physical_tau0_preconditions(
    *,
    driver,
    commission_bundle,
    sensor_apply_receipts=None,
) -> dict:
    """Validate every zero-motion prerequisite for physical tau0 capture."""
    bundle_path=Path(commission_bundle)
    bundle=_load_bundle(bundle_path)

    if bundle.get("status")!="PASS":
        raise RuntimeError("commissioning evidence bundle did not pass")

    commissioning_behavior=require_commissioning_behavior(bundle)
    commissioning_behavior_witness=commissioning_behavior["normalized"]
    commissioning_behavior_sha256=commissioning_behavior["sha256"]
    commission_bundle_sha256=hashlib.sha256(bundle_path.read_bytes()).hexdigest()

    commissioning_identity=bundle.get("hardware_identity") or {}
    expected=str(commissioning_identity.get("identity_sha256") or "")
    if not expected:
        raise RuntimeError("commissioning evidence bundle missing hardware identity")

    preflight=bundle.get("preflight")
    if not isinstance(preflight,dict):
        raise RuntimeError("commissioning evidence bundle missing read-only preflight lineage")
    preflight_receipt_sha256=str(preflight.get("receipt_sha256") or "")
    preflight_identity_sha256=str(preflight.get("hardware_identity_sha256") or "")
    gateway_contract_sha256=str(preflight.get("gateway_contract_sha256") or "")
    if not is_sha256(preflight_receipt_sha256):
        raise RuntimeError("commissioning evidence bundle has invalid preflight receipt SHA-256")
    if not is_sha256(gateway_contract_sha256):
        raise RuntimeError("commissioning evidence bundle has invalid gateway contract SHA-256")
    if preflight_identity_sha256!=expected:
        raise RuntimeError(
            "preflight hardware identity does not match commissioning hardware identity"
        )

    thingmodel_lineage=require_hardware_thingmodel_lineage(
        commissioning_identity,
        label="commissioning hardware identity",
    )
    site_lineage=require_hardware_site_lineage(
        commissioning_identity,
        label="commissioning hardware identity",
    )

    readiness=driver.physical_readiness()
    if not isinstance(readiness,dict):
        raise RuntimeError("WindowPilot physical readiness returned invalid payload")
    if readiness.get("capture_preconditions") is not True:
        reasons="; ".join(readiness.get("reasons") or [])
        raise RuntimeError(
            "WindowPilot physical capture preconditions not met"
            +((": "+reasons) if reasons else "")
        )
    if readiness.get("physical_write_ready") is not True:
        blockers="; ".join(readiness.get("write_blockers") or [])
        raise RuntimeError(
            "WindowPilot physical write gate is not ready"
            +((": "+blockers) if blockers else "")
        )

    runtime_identity=readiness.get("hardware_identity") or {}
    current=str(runtime_identity.get("identity_sha256") or "")
    if not current or current!=expected:
        raise RuntimeError(
            "commissioned hardware identity does not match current WindowPilot runtime"
        )
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

    sensor_evidence=build_sensor_evidence(
        readiness=readiness,
        site_lineage=site_lineage,
        commissioning_identity_sha256=expected,
        commissioning_bundle_sha256=commission_bundle_sha256,
        sensor_apply_receipts=sensor_apply_receipts,
    )

    caps=driver.capabilities()
    if caps.simulated:
        raise RuntimeError("WindowPilot execution is still simulated; physical capture aborted")
    if not caps.measured_position:
        raise RuntimeError(
            "WindowPilot has no measured position feedback; physical capture aborted"
        )

    return {
        "status":"PASS",
        "ready_for_tau0":True,
        "motion_performed":False,
        "commissioning_bundle_sha256":commission_bundle_sha256,
        "commissioning_identity_sha256":expected,
        "commissioning_hardware_identity":commissioning_identity,
        "runtime_hardware_identity":runtime_identity,
        "thingmodel_lineage":thingmodel_lineage,
        "site_lineage":site_lineage,
        "preflight_receipt_sha256":preflight_receipt_sha256,
        "preflight_hardware_identity_sha256":preflight_identity_sha256,
        "gateway_contract_sha256":gateway_contract_sha256,
        "commissioning_behavior_witness":commissioning_behavior_witness,
        "commissioning_behavior_sha256":commissioning_behavior_sha256,
        "sensor_evidence_origin":sensor_evidence["sensor_evidence_origin"],
        "runtime_sensor_lineage":sensor_evidence["runtime_sensor_lineage"],
        "sensor_staging_lineage":sensor_evidence["sensor_staging_lineage"],
        "sensor_evidence_sha256":sensor_evidence["sensor_evidence_sha256"],
        "driver_capabilities":asdict(caps),
    }
