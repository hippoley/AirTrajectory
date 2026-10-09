"""Create a verifiable public-upstream IFC evidence receipt.

A BLOCKED engineering gate is a valid, auditable test outcome but NEVER a
successful end-to-end physical run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def build_receipt(source: Path, readiness: dict, *, source_url: str) -> dict:
    raw = source.read_bytes()
    if not raw.startswith(b"ISO-10303-21;"):
        raise ValueError("upstream payload is not a STEP/IFC exchange file")
    if not isinstance(readiness, dict) or readiness.get("status") not in ("READY", "BLOCKED"):
        raise ValueError("missing valid upstream IFC readiness verdict")
    sha = hashlib.sha256(raw).hexdigest()
    if readiness.get("source", {}).get("sha256") not in (None, sha):
        raise ValueError("readiness source SHA differs from downloaded upstream bytes")
    blockers = readiness.get("blockers")
    if not isinstance(blockers, list):
        raise ValueError("IFC readiness must disclose blockers")
    control_ready = readiness["status"] == "READY" and not blockers
    payload = {
        "schema_version": "airtrajectory-public-upstream-gate-v0.1",
        "upstream_source_url": source_url,
        "upstream_source_sha256": sha,
        "upstream_size_bytes": len(raw),
        "readiness_status": readiness["status"],
        "readiness_blockers": blockers,
        "control_ready": control_ready,
        "contam_physics_executed": False,
        "e2e_status": "BLOCKED_PENDING_REAL_PRJ_AND_SOLVER_EXECUTION",
        "evidence_boundary": "actual public IFC input and importer readiness only; not CONTAM solver or physical actuator proof",
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return {**payload, "receipt_sha256": hashlib.sha256(canonical).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("readiness", type=Path)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    receipt = build_receipt(
        args.source,
        json.loads(args.readiness.read_text(encoding="utf-8")),
        source_url=args.source_url,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"receipt_sha256": receipt["receipt_sha256"], "e2e_status": receipt["e2e_status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
