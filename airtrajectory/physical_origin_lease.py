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
import socket
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
    owner_host=None,
    owner_pid=None,
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

    host=str(owner_host or socket.gethostname())
    pid=int(os.getpid() if owner_pid is None else owner_pid)
    if not host:
        raise ValueError("execution lease owner_host must be non-empty")
    if pid<=0:
        raise ValueError("execution lease owner_pid must be positive")

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
        "owner_host":host,
        "owner_pid":pid,
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


def _default_process_alive(pid: int) -> bool:
    try:
        os.kill(int(pid),0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        # Fail closed when the platform cannot prove the process is gone.
        return True
    return True


def recover_abandoned_physical_origin_execution(
    *,
    lease_path,
    recovered_at,
    recovery_host=None,
    process_alive_fn=None,
) -> dict[str, Any]:
    """Seal a dead-owner IN_FLIGHT lease as RECOVERY_REQUIRED.

    This never reopens the old physical origin. It is deliberately limited to
    same-host recovery where the owner PID can be proven absent.
    """
    current=verify_physical_origin_execution_lease(
        lease_path=lease_path,
    )
    if current["status"]!="IN_FLIGHT":
        raise RuntimeError(
            "only an IN_FLIGHT physical origin execution lease can be recovered"
        )

    owner_host=str(current.get("owner_host") or "")
    owner_pid=current.get("owner_pid")
    if not owner_host or owner_pid is None:
        raise RuntimeError(
            "execution lease lacks owner metadata required for safe recovery"
        )
    try:
        owner_pid=int(owner_pid)
    except (TypeError,ValueError) as exc:
        raise RuntimeError("execution lease owner_pid is invalid") from exc
    if owner_pid<=0:
        raise RuntimeError("execution lease owner_pid is invalid")

    host=str(recovery_host or socket.gethostname())
    if host!=owner_host:
        raise RuntimeError(
            "cannot prove abandoned execution lease owner is dead across hosts"
        )

    checker=process_alive_fn or _default_process_alive
    if checker(owner_pid):
        raise RuntimeError(
            "physical origin execution lease owner process is still running"
        )

    recovered_ts=float(recovered_at)
    if recovered_ts<=float(current["claimed_at"]):
        raise ValueError("recovered_at must be newer than claimed_at")

    return finalize_physical_origin_execution(
        lease_path=lease_path,
        status="RECOVERY_REQUIRED",
        finalized_at=recovered_ts,
        recovery={
            "reason":"OWNER_PROCESS_NOT_RUNNING",
            "requires_new_physical_origin":True,
            "abandoned_owner_host":owner_host,
            "abandoned_owner_pid":owner_pid,
            "recovered_at":recovered_ts,
            "evidence_boundary":(
                "same-host dead-owner recovery only; the old physical origin "
                "remains permanently consumed and must not be replayed"
            ),
        },
    )


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
    owner_host=payload.get("owner_host")
    owner_pid=payload.get("owner_pid")
    if (owner_host is None)!=(owner_pid is None):
        raise RuntimeError(
            "physical origin execution lease owner metadata is incomplete"
        )
    if owner_host is not None:
        if not str(owner_host):
            raise RuntimeError(
                "physical origin execution lease owner_host is invalid"
            )
        try:
            parsed_owner_pid=int(owner_pid)
        except (TypeError,ValueError) as exc:
            raise RuntimeError(
                "physical origin execution lease owner_pid is invalid"
            ) from exc
        if parsed_owner_pid<=0:
            raise RuntimeError(
                "physical origin execution lease owner_pid is invalid"
            )

    status=str(payload.get("status") or "")
    if status not in {"IN_FLIGHT","ADVANCED","RECOVERY_REQUIRED"}:
        raise RuntimeError("physical origin execution lease status is invalid")
    return {**payload,"lease_path":str(path)}
