"""Deterministic binding for a set of execution evidence envelopes."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping


_RESULT_ORDER = {
    "PASS": 0,
    "BLOCKED": 1,
    "FAIL": 2,
    "UNCERTAIN": 3,
    "NOT_EVALUATED": 4,
}


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _aggregate(results: list[str]) -> str:
    if not results:
        raise ValueError("evidence set requires at least one record")
    unknown=[value for value in results if value not in _RESULT_ORDER]
    if unknown:
        raise ValueError(f"unsupported evidence result: {unknown[0]}")
    return max(results,key=lambda value:_RESULT_ORDER[value])


def build_execution_evidence_set(
    records: Iterable[Mapping[str, Any]],
    *,
    suite_id: str,
) -> dict[str, Any]:
    """Freeze membership and aggregate semantics before higher-level signing."""
    rows=[]
    seen=set()
    for record in records:
        if record.get("record_type")!="execution-evidence-envelope-v0.1":
            raise ValueError("unsupported execution evidence record type")
        execution_id=str(record.get("execution_id") or "")
        if not execution_id:
            raise ValueError("execution evidence lacks execution_id")
        if execution_id in seen:
            raise ValueError(f"duplicate execution_id: {execution_id}")
        seen.add(execution_id)

        result=str(record.get("result") or "")
        harness_status=str(record.get("harness_status") or "")
        if result not in _RESULT_ORDER:
            raise ValueError("unsupported execution result")
        if harness_status not in {"COMPLETED","ERROR","INTERRUPTED"}:
            raise ValueError("unsupported harness_status")

        rows.append({
            "execution_id":execution_id,
            "record_sha256":_sha256(record),
            "result":result,
            "harness_status":harness_status,
        })

    rows.sort(key=lambda row:row["execution_id"])
    results=[row["result"] for row in rows]
    counts={name:0 for name in _RESULT_ORDER}
    for result in results:
        counts[result]+=1

    manifest={
        "schema_version":"0.1",
        "record_type":"execution-evidence-set-v0.1",
        "suite_id":str(suite_id),
        "record_count":len(rows),
        "records":rows,
        "counts":counts,
        "aggregate_result":_aggregate(results),
        "evidence_boundary":(
            "deterministic membership binding over execution evidence envelopes; "
            "this manifest is suitable as a pre-signing input but does not itself "
            "provide authenticity or digital signature guarantees"
        ),
    }
    manifest["manifest_sha256"]=_sha256(manifest)
    validate_execution_evidence_set(manifest)
    return manifest


def validate_execution_evidence_set(manifest: Mapping[str, Any]) -> None:
    if manifest.get("schema_version")!="0.1":
        raise ValueError("unsupported evidence set schema_version")
    if manifest.get("record_type")!="execution-evidence-set-v0.1":
        raise ValueError("unsupported evidence set record_type")

    rows=manifest.get("records")
    if not isinstance(rows,list) or not rows:
        raise ValueError("evidence set requires records")

    ids=[str(row.get("execution_id") or "") for row in rows]
    if ids!=sorted(ids):
        raise ValueError("evidence set membership is not deterministically ordered")
    if len(ids)!=len(set(ids)):
        raise ValueError("duplicate execution_id in evidence set")

    results=[str(row.get("result") or "") for row in rows]
    if manifest.get("aggregate_result")!=_aggregate(results):
        raise ValueError("aggregate_result does not match member results")

    expected_counts={name:results.count(name) for name in _RESULT_ORDER}
    if manifest.get("counts")!=expected_counts:
        raise ValueError("counts do not match member results")
    if manifest.get("record_count")!=len(rows):
        raise ValueError("record_count does not match membership")

    unsigned=dict(manifest)
    supplied=str(unsigned.pop("manifest_sha256",""))
    if supplied!=_sha256(unsigned):
        raise ValueError("evidence set manifest_sha256 mismatch")
