"""Durable local execution leases for physical-origin receipts.

A physical origin is single-use for real execution. Claiming uses O_EXCL so
separate CLI processes cannot both consume the same origin on one filesystem.

This is a local orchestration guarantee, not a distributed transaction or a
substitute for gateway/device-side durable idempotency.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping


def _sha256(payload: Any) -> str:
    raw=json.dumps(
        payload,
        sort_keys=True,
        separators=(",",":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _require_sha(value: Any, label: str) -> str:
    text=str(value or "")
    if len(text)!=64 or any(ch not in "0123456789abcdef" for ch in text.lower()):
        raise RuntimeError(f"{label} must be a 64-character SHA-256")
    return text.lower()


def _lease_path(lease_dir, origin_receipt_sha256: str) -> Path:
    root=Path(lease_dir)
    return root/f"{origin_receipt_sha256}.json"


def claim_physical_origin_execution(
    *,
    lease_dir,
    origin_receipt_sha256,
    origin_sha256,
    planner_receipt_sha256,
    planner_step_sha256,
    opening_id,
    zone_id,
    claimed_at,
) -> dict[str, Any]:
    receipt_sha=_require_sha(
        origin_receipt_sha256,
        "physical origin receipt",
    )
    origin_sha=_require_sha(origin_sha256,"physical origin state")
    planner_sha=_require_sha(planner_receipt_sha256,"planner receipt")
    step_sha=_require_sha(planner_step_sha256,"planner step")
    ts=float(claimed_at)
    if ts<=0:
        raise ValueError("claimed_at must be positive")
    opening=str(opening_id or "")
    zone=str(zone_id or "")
    if not opening or not zone:
        raise ValueError("execution lease requires opening_id and zone_id")

    path=_lease_path(lease_dir,receipt_sha)
    path.parent.mkdir(parents=True,exist_ok=True)
    payload={
        "schema_version":"0.1",
        "lease":"physical-origin-execution-lease-v1",
        "status":"IN_FLIGHT",
        "physical_origin_receipt_sha256":receipt_sha,
        "physical_origin_sha256":origin_sha,
        "planner_receipt_sha256":planner_sha,
        "planner_step_sha256":step_sha,
        "opening_id":opening,
        "zone_id":zone,
        "claimed_at":ts,
        "evidence_boundary":(
            "local filesystem single-use execution lease; not a distributed "
            "gateway/device transaction guarantee"
        ),
    }
    record={**payload,"lease_sha256":_sha256(payload)}
    encoded=(json.dumps(record,ensure_ascii=False,indent=2,sort_keys=True)+"\n").encode(
        "utf-8"
    )

    try:
        fd=os.open(
            str(path),
            os.O_WRONLY|os.O_CREAT|os.O_EXCL,
            0o600,
        )
    except FileExistsError as exc:
        try:
            existing=json.loads(path.read_text(encoding="utf-8"))
            status=str(existing.get("status") or "UNKNOWN")
        except Exception:
            status="UNREADABLE"
        raise RuntimeError(
            "physical origin has already been claimed for execution "
            f"(lease status={status})"
        ) from exc

    try:
        with os.fdopen(fd,"wb") as fh:
            fh.write(encoded)
            fh.flush()
            os.fsync(fh.fileno())
    except Exception:
        # If persistence itself fails, retain any created lease file whenever
        # possible; fail closed rather than reopening the origin for replay.
        raise

    return {**record,"lease_path":str(path)}


def finalize_physical_origin_execution(
    *,
    lease_path,
    status: str,
    finalized_at,
    next_origin_receipt_sha256=None,
    step_summary_sha256=None,
    recovery=None,
) -> dict[str, Any]:
    path=Path(lease_path)
    if not path.exists():
        raise RuntimeError("physical origin execution lease is missing")
    current=json.loads(path.read_text(encoding="utf-8"))
    provided=str(current.get("lease_sha256") or "")
    current_payload={
        key:value
        for key,value in current.items()
        if key!="lease_sha256"
    }
    if provided!=_sha256(current_payload):
        raise RuntimeError("physical origin execution lease SHA-256 mismatch")
    if current.get("status")!="IN_FLIGHT":
        raise RuntimeError("physical origin execution lease is not IN_FLIGHT")

    normalized_status=str(status or "").upper()
    if normalized_status not in {"ADVANCED","RECOVERY_REQUIRED"}:
        raise ValueError("lease final status must be ADVANCED or RECOVERY_REQUIRED")
    ts=float(finalized_at)
    if ts<=float(current["claimed_at"]):
        raise ValueError("finalized_at must be newer than claimed_at")

    payload={
        key:value
        for key,value in current.items()
        if key!="lease_sha256"
    }
    payload["status"]=normalized_status
    payload["finalized_at"]=ts
    if normalized_status=="ADVANCED":
        payload["next_physical_origin_receipt_sha256"]=_require_sha(
            next_origin_receipt_sha256,
            "next physical origin receipt",
        )
        payload["step_summary_sha256"]=_require_sha(
            step_summary_sha256,
            "replanned physical step summary",
        )
        payload["recovery"]=None
    else:
        payload["next_physical_origin_receipt_sha256"]=None
        payload["step_summary_sha256"]=(
            None
            if step_summary_sha256 is None
            else _require_sha(
                step_summary_sha256,
                "replanned physical step summary",
            )
        )
        payload["recovery"]=dict(recovery or {})

    final={**payload,"lease_sha256":_sha256(payload)}
    temp=path.with_suffix(path.suffix+".tmp")
    temp.write_text(
        json.dumps(final,ensure_ascii=False,indent=2,sort_keys=True)+"\n",
        encoding="utf-8",
    )
    with temp.open("rb") as fh:
        os.fsync(fh.fileno())
    os.replace(temp,path)
    return {**final,"lease_path":str(path)}


def record_physical_origin_recovery(
    *,
    lease_path,
    recovered_at,
    recovery_origin_sha256,
    recovery_origin_receipt_sha256,
    recovery_summary_sha256=None,
) -> dict[str, Any]:
    path=Path(lease_path)
    if not path.exists():
        raise RuntimeError("physical origin execution lease is missing")
    current=json.loads(path.read_text(encoding="utf-8"))
    provided=str(current.get("lease_sha256") or "")
    body={key:value for key,value in current.items() if key!="lease_sha256"}
    if provided!=_sha256(body):
        raise RuntimeError("physical origin execution lease SHA-256 mismatch")
    if current.get("status")!="RECOVERY_REQUIRED":
        raise RuntimeError(
            "only a RECOVERY_REQUIRED physical origin lease can be recovered"
        )
    ts=float(recovered_at)
    finalized_at=float(current.get("finalized_at") or 0)
    if ts<=finalized_at:
        raise ValueError("recovered_at must be newer than lease finalized_at")

    payload=dict(body)
    payload["status"]="RECOVERED"
    payload["recovered_at"]=ts
    payload["recovery_origin_sha256"]=_require_sha(
        recovery_origin_sha256,
        "recovery physical origin state",
    )
    payload["recovery_origin_receipt_sha256"]=_require_sha(
        recovery_origin_receipt_sha256,
        "recovery physical origin receipt",
    )
    payload["recovery_summary_sha256"]=(
        None
        if recovery_summary_sha256 is None
        else _require_sha(
            recovery_summary_sha256,
            "physical recovery summary",
        )
    )
    final={**payload,"lease_sha256":_sha256(payload)}
    temp=path.with_suffix(path.suffix+".tmp")
    temp.write_text(
        json.dumps(final,ensure_ascii=False,indent=2,sort_keys=True)+"\n",
        encoding="utf-8",
    )
    with temp.open("rb") as fh:
        os.fsync(fh.fileno())
    os.replace(temp,path)
    return {**final,"lease_path":str(path)}


def verify_physical_origin_execution_lease(
    *,
    lease_path,
    expected_origin_receipt_sha256=None,
) -> dict[str, Any]:
    path=Path(lease_path)
    payload=json.loads(path.read_text(encoding="utf-8"))
    provided=str(payload.get("lease_sha256") or "")
    body={key:value for key,value in payload.items() if key!="lease_sha256"}
    if provided!=_sha256(body):
        raise RuntimeError("physical origin execution lease SHA-256 mismatch")
    if payload.get("lease")!="physical-origin-execution-lease-v1":
        raise RuntimeError("unsupported physical origin execution lease")
    receipt_sha=_require_sha(
        payload.get("physical_origin_receipt_sha256"),
        "physical origin receipt",
    )
    if (
        expected_origin_receipt_sha256 is not None
        and receipt_sha!=_require_sha(
            expected_origin_receipt_sha256,
            "expected physical origin receipt",
        )
    ):
        raise RuntimeError("execution lease does not belong to expected physical origin")
    status=str(payload.get("status") or "")
    if status not in {"IN_FLIGHT","ADVANCED","RECOVERY_REQUIRED","RECOVERED"}:
        raise RuntimeError("physical origin execution lease status is invalid")
    return {**payload,"lease_path":str(path)}
