"""Independent verification of persisted physical tau0 artifacts.

This module does not contact hardware and does not create evidence. It re-checks
that the persisted trajectory, audit receipt, and commissioning bundle still
form one internally consistent evidence chain.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


_HEX=set("0123456789abcdefABCDEF")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_sha256(value) -> bool:
    text=str(value or "")
    return len(text)==64 and all(ch in _HEX for ch in text)


def _load_json(path: Path):
    payload=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload,dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _load_trajectory_record(path: Path, trajectory_id: str):
    matches=[]
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload=json.loads(line)
        if isinstance(payload,dict) and payload.get("id")==trajectory_id:
            matches.append(payload)
    if not matches:
        raise ValueError(f"trajectory id not found in {path}: {trajectory_id}")
    if len(matches)!=1:
        raise ValueError(f"trajectory id appears multiple times in {path}: {trajectory_id}")
    return matches[0]


def verify_physical_tau0_artifacts(*, trajectory_path, receipt_path, commission_bundle_path):
    trajectory_path=Path(trajectory_path)
    receipt_path=Path(receipt_path)
    commission_bundle_path=Path(commission_bundle_path)
    reasons=[]

    for label,path in (
        ("trajectory",trajectory_path),
        ("receipt",receipt_path),
        ("commissioning bundle",commission_bundle_path),
    ):
        if not path.exists():
            reasons.append(f"{label} file does not exist: {path}")

    if reasons:
        return {"valid_artifacts":False,"reasons":reasons}

    try:
        receipt=_load_json(receipt_path)
    except Exception as exc:
        return {"valid_artifacts":False,"reasons":[f"cannot read tau0 receipt: {exc}"]}

    if receipt.get("valid_tau0") is not True:
        reasons.append("tau0 receipt does not declare valid_tau0=true")
    if receipt.get("environment_kind")!="physical":
        reasons.append("tau0 receipt environment_kind is not physical")

    trajectory_sha=_sha256(trajectory_path)
    receipt_sha=_sha256(receipt_path)
    commission_sha=_sha256(commission_bundle_path)

    expected_trajectory_sha=str(receipt.get("trajectory_sha256") or "")
    expected_commission_sha=str(receipt.get("commissioning_bundle_sha256") or "")
    if not _is_sha256(expected_trajectory_sha):
        reasons.append("tau0 receipt has invalid trajectory SHA-256")
    elif trajectory_sha!=expected_trajectory_sha:
        reasons.append("trajectory file SHA-256 does not match tau0 receipt")

    if not _is_sha256(expected_commission_sha):
        reasons.append("tau0 receipt has invalid commissioning bundle SHA-256")
    elif commission_sha!=expected_commission_sha:
        reasons.append("commissioning bundle SHA-256 does not match tau0 receipt")

    commissioning_id=str(receipt.get("commissioning_identity_sha256") or "")
    runtime_identity=receipt.get("runtime_hardware_identity") or {}
    runtime_id=runtime_identity.get("identity_sha256") if isinstance(runtime_identity,dict) else None
    preflight_id=str(receipt.get("preflight_hardware_identity_sha256") or "")
    preflight_receipt_sha=str(receipt.get("preflight_receipt_sha256") or "")
    gateway_contract_sha=str(receipt.get("gateway_contract_sha256") or "")

    if not commissioning_id:
        reasons.append("tau0 receipt missing commissioning hardware identity")
    if runtime_id!=commissioning_id:
        reasons.append("runtime hardware identity does not match commissioning identity")
    if preflight_id!=commissioning_id:
        reasons.append("preflight hardware identity does not match commissioning identity")
    if not _is_sha256(preflight_receipt_sha):
        reasons.append("tau0 receipt has invalid preflight receipt SHA-256")
    if not _is_sha256(gateway_contract_sha):
        reasons.append("tau0 receipt has invalid gateway contract SHA-256")

    try:
        bundle=_load_json(commission_bundle_path)
        if bundle.get("status")!="PASS":
            reasons.append("commissioning bundle status is not PASS")
        bundle_id=(bundle.get("hardware_identity") or {}).get("identity_sha256")
        if bundle_id!=commissioning_id:
            reasons.append("commissioning bundle hardware identity does not match tau0 receipt")
        lineage=bundle.get("preflight") or {}
        if lineage.get("receipt_sha256")!=preflight_receipt_sha:
            reasons.append("commissioning bundle preflight receipt lineage mismatch")
        if lineage.get("hardware_identity_sha256")!=preflight_id:
            reasons.append("commissioning bundle preflight hardware identity mismatch")
        if lineage.get("gateway_contract_sha256")!=gateway_contract_sha:
            reasons.append("commissioning bundle gateway contract lineage mismatch")
    except Exception as exc:
        reasons.append(f"cannot validate commissioning bundle: {exc}")

    trajectory_id=str(receipt.get("trajectory_id") or "")
    if not trajectory_id:
        reasons.append("tau0 receipt missing trajectory_id")
    else:
        try:
            trajectory=_load_trajectory_record(trajectory_path,trajectory_id)
            if trajectory.get("environment_kind")!="physical":
                reasons.append("persisted trajectory environment_kind is not physical")
            context=trajectory.get("context") or {}
            if context.get("commissioning_identity_sha256")!=commissioning_id:
                reasons.append("trajectory commissioning identity lineage mismatch")
            traj_runtime=context.get("runtime_hardware_identity") or {}
            if not isinstance(traj_runtime,dict) or traj_runtime.get("identity_sha256")!=runtime_id:
                reasons.append("trajectory runtime hardware identity lineage mismatch")
            if context.get("commissioning_bundle_sha256")!=expected_commission_sha:
                reasons.append("trajectory commissioning bundle lineage mismatch")
            if context.get("preflight_receipt_sha256")!=preflight_receipt_sha:
                reasons.append("trajectory preflight receipt lineage mismatch")
            if context.get("preflight_hardware_identity_sha256")!=preflight_id:
                reasons.append("trajectory preflight hardware identity lineage mismatch")
            if context.get("gateway_contract_sha256")!=gateway_contract_sha:
                reasons.append("trajectory gateway contract lineage mismatch")

            steps=trajectory.get("steps") or []
            if len(steps)!=int(receipt.get("steps") or 0):
                reasons.append("persisted trajectory step count does not match tau0 receipt")
            if not steps:
                reasons.append("persisted trajectory has no steps")

            for index,step in enumerate(steps):
                sensor_types={
                    item.get("sensor_type")
                    for item in (step.get("sensor_readings") or [])
                    if isinstance(item,dict)
                }
                if "co2" not in sensor_types:
                    reasons.append(f"step {index} missing CO2 evidence")
                if "rain" not in sensor_types:
                    reasons.append(f"step {index} missing rain evidence")

                feedback=[
                    item for item in (step.get("actuator_feedback") or [])
                    if isinstance(item,dict)
                ]
                if not feedback:
                    reasons.append(f"step {index} missing actuator feedback")
                    feedback_ts=None
                else:
                    if any(item.get("measured_position_pct") is None for item in feedback):
                        reasons.append(f"step {index} lacks measured actuator position")
                    timestamps=[float(item.get("timestamp") or 0) for item in feedback]
                    if any(ts<=0 for ts in timestamps):
                        reasons.append(f"step {index} actuator feedback missing timestamp")
                    feedback_ts=max(timestamps) if timestamps else None

                next_readings=[
                    item for item in (step.get("next_sensor_readings") or [])
                    if isinstance(item,dict)
                ]
                next_types={item.get("sensor_type") for item in next_readings}
                if "co2" not in next_types:
                    reasons.append(f"step {index} missing post-action CO2 evidence")
                if "rain" not in next_types:
                    reasons.append(f"step {index} missing post-action rain evidence")
                if feedback_ts is not None:
                    for item in next_readings:
                        if item.get("sensor_type") in ("co2","rain"):
                            if float(item.get("timestamp") or 0)<=feedback_ts:
                                reasons.append(
                                    f"step {index} post-action sensor evidence is not newer than actuator feedback"
                                )
                                break
        except Exception as exc:
            reasons.append(f"cannot validate persisted trajectory: {exc}")

    return {
        "valid_artifacts":not reasons,
        "reasons":reasons,
        "trajectory_id":trajectory_id or None,
        "trajectory_sha256":trajectory_sha,
        "receipt_sha256":receipt_sha,
        "commissioning_bundle_sha256":commission_sha,
        "commissioning_identity_sha256":commissioning_id or None,
        "runtime_hardware_identity_sha256":runtime_id,
        "preflight_receipt_sha256":preflight_receipt_sha or None,
        "gateway_contract_sha256":gateway_contract_sha or None,
    }
