"""Physical sensor source lineage for WindowPilot -> AirTrajectory.

Two evidence levels are deliberately distinct.

runtime-measured-lineage:
    Live WindowPilot proves fresh + measured + ThingModel/site-bound CO2/rain
    and exposes source/timestamp/quality lineage. This remains transport-neutral.

probe-apply-audited:
    The same live evidence is additionally tied to one PASS WindowPilot
    sensor_apply receipt for CO2 and one for rain. The receipts must prove
    observe-only staging, zero actuator/window commands, the same commissioned
    hardware/site, and the same live sensor-contract SHA.

A source string such as sensor-read-probe:<sha> is descriptive only. It never
upgrades evidence to audited without the corresponding apply receipts.
"""
from __future__ import annotations

import hashlib
import json
from math import isfinite
from pathlib import Path

from .lineage import is_sha256, sensor_binding_matches_site, sensor_binding_valid


_REQUIRED=(("co2","co2_ppm"),("rain","rain"))


def _canonical_sha256(payload) -> str:
    raw=json.dumps(
        payload,
        sort_keys=True,
        separators=(",",":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _file_sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load_json(path,label):
    p=Path(path)
    if not p.exists():
        raise RuntimeError(f"{label} does not exist: {p}")
    try:
        payload=json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"{label} is not valid JSON: {p}") from exc
    if not isinstance(payload,dict):
        raise RuntimeError(f"{label} must be a JSON object")
    return payload


def _normalize_lineage_entry(entry, *, role, runtime_key, site_lineage):
    if not isinstance(entry,dict):
        raise RuntimeError(f"WindowPilot readiness missing {runtime_key} sensor lineage")

    for flag in ("fresh","measured","registry_bound","site_bound"):
        if entry.get(flag) is not True:
            raise RuntimeError(
                f"WindowPilot {runtime_key} sensor lineage does not prove {flag}=true"
            )

    try:
        timestamp=float(entry.get("timestamp"))
    except Exception as exc:
        raise RuntimeError(
            f"WindowPilot {runtime_key} sensor lineage timestamp is missing/invalid"
        ) from exc
    if not isfinite(timestamp) or timestamp<=0:
        raise RuntimeError(
            f"WindowPilot {runtime_key} sensor lineage timestamp must be positive"
        )

    quality=str(entry.get("quality") or "").strip()
    source=str(entry.get("source") or "").strip()
    if not quality:
        raise RuntimeError(f"WindowPilot {runtime_key} sensor lineage missing quality")
    if not source:
        raise RuntimeError(f"WindowPilot {runtime_key} sensor lineage missing source")

    binding=entry.get("thingmodel_binding")
    if not sensor_binding_valid(binding):
        raise RuntimeError(
            f"WindowPilot {runtime_key} sensor lineage missing valid ThingModel/site binding"
        )
    if not sensor_binding_matches_site(binding,site_lineage):
        raise RuntimeError(
            f"WindowPilot {runtime_key} sensor lineage belongs to a different physical site"
        )

    property_name=str(binding.get("property") or "")
    if role=="co2" and property_name!="airSensor.co2":
        raise RuntimeError(
            "WindowPilot CO2 sensor lineage is not bound to airSensor.co2"
        )
    if role=="rain" and property_name!="rainSensor.rainDetect":
        raise RuntimeError(
            "WindowPilot rain sensor lineage is not bound to rainSensor.rainDetect"
        )

    scheme=str(entry.get("source_scheme") or "").strip()
    contract_sha=entry.get("source_contract_sha256")
    if scheme=="sensor-read-probe":
        if not is_sha256(contract_sha):
            raise RuntimeError(
                f"WindowPilot {runtime_key} sensor-read-probe lineage has invalid contract SHA-256"
            )
        contract_sha=str(contract_sha).lower()
        if source!=f"sensor-read-probe:{contract_sha}":
            raise RuntimeError(
                f"WindowPilot {runtime_key} sensor source disagrees with source_contract_sha256"
            )
    elif scheme in ("measured-runtime-source",""):
        scheme="measured-runtime-source"
        if contract_sha not in (None,""):
            raise RuntimeError(
                f"WindowPilot {runtime_key} generic measured source must not claim a probe contract SHA"
            )
        contract_sha=None
    else:
        raise RuntimeError(
            f"WindowPilot {runtime_key} sensor lineage has unsupported source_scheme: {scheme}"
        )

    return {
        "role":role,
        "runtime_key":runtime_key,
        "timestamp":timestamp,
        "quality":quality,
        "source":source,
        "source_scheme":scheme,
        "source_contract_sha256":contract_sha,
        "thingmodel_binding":dict(binding),
    }


def normalize_runtime_sensor_lineage(readiness, site_lineage) -> dict:
    if not isinstance(readiness,dict):
        raise RuntimeError("WindowPilot physical readiness must be an object")
    raw=readiness.get("sensor_evidence_lineage")
    if not isinstance(raw,dict):
        raise RuntimeError(
            "WindowPilot physical readiness missing sensor_evidence_lineage; "
            "upgrade WindowPilot before physical tau0 capture"
        )

    normalized={}
    for role,runtime_key in _REQUIRED:
        normalized[role]=_normalize_lineage_entry(
            raw.get(runtime_key),
            role=role,
            runtime_key=runtime_key,
            site_lineage=site_lineage,
        )
    return normalized


def _base_origin(runtime_lineage) -> str:
    if all(
        runtime_lineage[role].get("source_scheme")=="sensor-read-probe"
        for role,_ in _REQUIRED
    ):
        return "probe-labeled"
    return "runtime-measured-lineage"


def _normalize_apply_receipt(
    payload,
    *,
    receipt_sha256,
    role,
    runtime_lineage,
    commissioning_identity_sha256,
    commissioning_bundle_sha256,
    site_lineage,
):
    if payload.get("status")!="PASS":
        raise RuntimeError(f"{role} sensor_apply receipt status is not PASS")
    expected_key="co2_ppm" if role=="co2" else "rain"
    if payload.get("role")!=role or payload.get("role_key")!=expected_key:
        raise RuntimeError(f"{role} sensor_apply receipt role mismatch")

    numeric_expect={
        "network_requests_by_tool":3,
        "runtime_posts_by_tool":1,
        "actuator_writes_by_tool":0,
        "window_command_endpoints_called":0,
    }
    for key,expected in numeric_expect.items():
        try:
            actual=int(payload.get(key))
        except Exception as exc:
            raise RuntimeError(
                f"{role} sensor_apply receipt missing/invalid {key}"
            ) from exc
        if actual!=expected:
            raise RuntimeError(
                f"{role} sensor_apply receipt {key}={actual}, expected {expected}"
            )

    if payload.get("automation_evaluated") is not False:
        raise RuntimeError(
            f"{role} sensor_apply receipt does not prove automation_evaluated=false"
        )
    if payload.get("actuator_command_issued") is not False:
        raise RuntimeError(
            f"{role} sensor_apply receipt does not prove actuator_command_issued=false"
        )

    checks=payload.get("runtime_sensor_checks")
    if not isinstance(checks,dict) or any(
        checks.get(key) is not True
        for key in ("fresh","measured","registry_bound","site_bound")
    ):
        raise RuntimeError(
            f"{role} sensor_apply receipt does not prove complete post-apply sensor readiness"
        )

    runtime_id=str(payload.get("runtime_hardware_identity_sha256") or "")
    if runtime_id!=commissioning_identity_sha256:
        raise RuntimeError(
            f"{role} sensor_apply runtime hardware identity does not match commissioning"
        )

    expected_site={
        "site_id":site_lineage.get("site_id"),
        "site_manifest_sha256":site_lineage.get("site_manifest_sha256"),
        "site_contract_sha256":site_lineage.get("site_contract_sha256"),
    }
    mismatched=[
        key for key,value in expected_site.items()
        if str(payload.get(key) or "")!=str(value or "")
    ]
    if mismatched:
        raise RuntimeError(
            f"{role} sensor_apply physical-site lineage mismatch: "
            +",".join(mismatched)
        )

    receipt_commission_sha=str(payload.get("commissioning_bundle_sha256") or "")
    if not is_sha256(receipt_commission_sha):
        raise RuntimeError(
            f"{role} sensor_apply receipt has invalid commissioning bundle SHA-256"
        )
    if receipt_commission_sha.lower()!=commissioning_bundle_sha256.lower():
        raise RuntimeError(
            f"{role} sensor_apply receipt belongs to a different commissioning bundle"
        )

    probe_receipt_sha=str(payload.get("probe_receipt_sha256") or "")
    sensor_contract_sha=str(payload.get("sensor_contract_sha256") or "")
    if not is_sha256(probe_receipt_sha):
        raise RuntimeError(
            f"{role} sensor_apply receipt has invalid probe receipt SHA-256"
        )
    if not is_sha256(sensor_contract_sha):
        raise RuntimeError(
            f"{role} sensor_apply receipt has invalid sensor contract SHA-256"
        )
    sensor_contract_sha=sensor_contract_sha.lower()

    live=runtime_lineage[role]
    if live.get("source_scheme")!="sensor-read-probe":
        raise RuntimeError(
            f"{role} live sensor source is not probe-labeled; cannot claim probe-apply-audited"
        )
    if live.get("source_contract_sha256")!=sensor_contract_sha:
        raise RuntimeError(
            f"{role} live sensor contract SHA does not match sensor_apply receipt"
        )

    try:
        sample_timestamp=float(payload.get("sample_timestamp"))
    except Exception as exc:
        raise RuntimeError(
            f"{role} sensor_apply receipt sample_timestamp is missing/invalid"
        ) from exc
    if not isfinite(sample_timestamp) or sample_timestamp <= 0:
        raise RuntimeError(f"{role} sensor_apply sample_timestamp must be finite and positive")
    if sample_timestamp!=float(live.get("timestamp")):
        raise RuntimeError(
            f"{role} live sensor timestamp does not match sensor_apply staged sample"
        )

    return {
        "role":role,
        "role_key":expected_key,
        "apply_receipt_sha256":receipt_sha256,
        "probe_receipt_sha256":probe_receipt_sha.lower(),
        "sensor_contract_sha256":sensor_contract_sha,
        "commissioning_bundle_sha256":receipt_commission_sha.lower(),
        "runtime_hardware_identity_sha256":runtime_id,
        "site_id":expected_site["site_id"],
        "site_manifest_sha256":expected_site["site_manifest_sha256"],
        "site_contract_sha256":expected_site["site_contract_sha256"],
        "sample_timestamp":sample_timestamp,
        "runtime_sensor_checks":{
            "fresh":True,
            "measured":True,
            "registry_bound":True,
            "site_bound":True,
        },
        "automation_evaluated":False,
        "actuator_command_issued":False,
        "network_requests_by_tool":3,
        "runtime_posts_by_tool":1,
        "actuator_writes_by_tool":0,
        "window_command_endpoints_called":0,
    }


def load_and_validate_sensor_apply_receipts(
    paths,
    *,
    runtime_lineage,
    commissioning_identity_sha256,
    commissioning_bundle_sha256,
    site_lineage,
):
    paths=list(paths or [])
    if not paths:
        return None
    if len(paths)!=2:
        raise RuntimeError(
            "probe-apply audit requires exactly two sensor_apply receipts: one CO2 and one rain"
        )

    staged={}
    for path in paths:
        payload=_load_json(path,"sensor_apply receipt")
        role=str(payload.get("role") or "")
        if role not in ("co2","rain"):
            raise RuntimeError(
                f"sensor_apply receipt has unsupported role: {role or 'missing'}"
            )
        if role in staged:
            raise RuntimeError(f"duplicate sensor_apply receipt for role: {role}")
        staged[role]=_normalize_apply_receipt(
            payload,
            receipt_sha256=_file_sha256(path),
            role=role,
            runtime_lineage=runtime_lineage,
            commissioning_identity_sha256=commissioning_identity_sha256,
            commissioning_bundle_sha256=commissioning_bundle_sha256,
            site_lineage=site_lineage,
        )

    missing=[role for role,_ in _REQUIRED if role not in staged]
    if missing:
        raise RuntimeError(
            "sensor_apply receipts missing required role(s): "+",".join(missing)
        )
    return {role:staged[role] for role,_ in _REQUIRED}


def _validate_staging_summary(
    staging,
    *,
    runtime_lineage,
    commissioning_identity_sha256,
    commissioning_bundle_sha256,
    site_lineage,
):
    if not isinstance(staging,dict):
        raise RuntimeError(
            "probe-apply-audited sensor evidence missing sensor_staging_lineage"
        )
    if set(staging)!={"co2","rain"}:
        raise RuntimeError(
            "probe-apply-audited staging lineage must contain exactly CO2 and rain"
        )

    normalized={}
    for role,_ in _REQUIRED:
        item=staging.get(role)
        if not isinstance(item,dict):
            raise RuntimeError(f"sensor staging lineage missing {role}")
        synthetic={
            **item,
            "status":"PASS",
            "role":role,
        }
        receipt_sha=str(item.get("apply_receipt_sha256") or "")
        if not is_sha256(receipt_sha):
            raise RuntimeError(
                f"{role} sensor staging lineage has invalid apply receipt SHA-256"
            )
        normalized[role]=_normalize_apply_receipt(
            synthetic,
            receipt_sha256=receipt_sha.lower(),
            role=role,
            runtime_lineage=runtime_lineage,
            commissioning_identity_sha256=commissioning_identity_sha256,
            commissioning_bundle_sha256=commissioning_bundle_sha256,
            site_lineage=site_lineage,
        )
    return normalized


def build_sensor_evidence(
    *,
    readiness,
    site_lineage,
    commissioning_identity_sha256,
    commissioning_bundle_sha256,
    sensor_apply_receipts=None,
):
    if not is_sha256(commissioning_bundle_sha256):
        raise RuntimeError("invalid commissioning bundle SHA-256")
    runtime_lineage=normalize_runtime_sensor_lineage(readiness,site_lineage)
    staging=load_and_validate_sensor_apply_receipts(
        sensor_apply_receipts,
        runtime_lineage=runtime_lineage,
        commissioning_identity_sha256=commissioning_identity_sha256,
        commissioning_bundle_sha256=commissioning_bundle_sha256,
        site_lineage=site_lineage,
    )
    origin=(
        "probe-apply-audited"
        if staging is not None
        else _base_origin(runtime_lineage)
    )
    core={
        "sensor_evidence_origin":origin,
        "runtime_sensor_lineage":runtime_lineage,
        "sensor_staging_lineage":staging,
    }
    return {
        **core,
        "sensor_evidence_sha256":_canonical_sha256(core),
    }


def validate_sensor_evidence_context(
    *,
    sensor_evidence_origin,
    runtime_sensor_lineage,
    sensor_staging_lineage,
    sensor_evidence_sha256,
    site_lineage,
    commissioning_identity_sha256,
    commissioning_bundle_sha256,
):
    if not isinstance(runtime_sensor_lineage,dict):
        raise RuntimeError("trajectory missing runtime_sensor_lineage")
    readiness_shape={"sensor_evidence_lineage":{}}
    for role,runtime_key in _REQUIRED:
        item=runtime_sensor_lineage.get(role)
        if not isinstance(item,dict):
            raise RuntimeError(f"trajectory runtime_sensor_lineage missing {role}")
        readiness_shape["sensor_evidence_lineage"][runtime_key]={
            **item,
            "fresh":True,
            "measured":True,
            "registry_bound":True,
            "site_bound":True,
        }
    normalized_runtime=normalize_runtime_sensor_lineage(
        readiness_shape,
        site_lineage,
    )
    if normalized_runtime!=runtime_sensor_lineage:
        raise RuntimeError(
            "trajectory runtime_sensor_lineage is not canonical"
        )

    origin=str(sensor_evidence_origin or "")
    if origin=="probe-apply-audited":
        normalized_staging=_validate_staging_summary(
            sensor_staging_lineage,
            runtime_lineage=normalized_runtime,
            commissioning_identity_sha256=commissioning_identity_sha256,
            commissioning_bundle_sha256=commissioning_bundle_sha256,
            site_lineage=site_lineage,
        )
        if normalized_staging!=sensor_staging_lineage:
            raise RuntimeError(
                "trajectory sensor_staging_lineage is not canonical"
            )
    else:
        if sensor_staging_lineage not in (None,{}):
            raise RuntimeError(
                "non-audited sensor evidence must not carry staging lineage"
            )
        expected=_base_origin(normalized_runtime)
        if origin!=expected:
            raise RuntimeError(
                f"sensor evidence origin mismatch: {origin!r} != {expected!r}"
            )

    core={
        "sensor_evidence_origin":origin,
        "runtime_sensor_lineage":normalized_runtime,
        "sensor_staging_lineage":sensor_staging_lineage,
    }
    calculated=_canonical_sha256(core)
    if calculated!=str(sensor_evidence_sha256 or ""):
        raise RuntimeError("sensor evidence context/hash mismatch")
    return core
