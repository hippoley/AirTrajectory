"""One-shot raw field log → aligned samples → validation pipeline."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .contam_field_capture import compile_field_capture_bundle
from .contam_field_validation import validate_contam_against_field
from .field_capture_import import import_field_capture
from .layout import LayoutContract


def _sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def run_field_validation_pipeline(
    *,
    layout: LayoutContract,
    runtime_receipt: dict[str, Any],
    protocol: dict[str, Any],
    manifest_path: str | Path,
    records_path: str | Path,
    records_format: str = "auto",
) -> tuple[dict[str, Any], dict[str, Any]]:
    imported = import_field_capture(
        manifest_path=manifest_path,
        records_path=records_path,
        records_format=records_format,
    )
    aligned = compile_field_capture_bundle(
        layout=layout,
        runtime_receipt=runtime_receipt,
        protocol=protocol,
        capture=imported,
    )
    validation = validate_contam_against_field(
        layout=layout,
        runtime_receipt=runtime_receipt,
        protocol=protocol,
        field_bundle=aligned,
    )

    aligned_sha = _sha256(aligned)
    payload = {
        "schema_version": "0.1",
        "pipeline": "field-validation-pipeline-v1",
        "status": validation["status"],
        "topology_id": layout.topology_id,
        "runtime_receipt_sha256": runtime_receipt[
            "runtime_receipt_sha256"
        ],
        "protocol_sha256": validation["protocol_sha256"],
        "source_records_sha256": validation["source_records_sha256"],
        "import_receipt_sha256": validation["import_receipt_sha256"],
        "raw_capture_sha256": validation["raw_capture_sha256"],
        "alignment_sha256": validation["alignment_sha256"],
        "aligned_bundle_sha256": aligned_sha,
        "field_validation_receipt_sha256": validation[
            "field_validation_receipt_sha256"
        ],
        "field_validation_verified": validation[
            "field_validation_verified"
        ],
        "engineering_truth": validation["engineering_truth"],
    }
    return (
        {
            **payload,
            "pipeline_receipt_sha256": _sha256(payload),
            "field_validation": validation,
        },
        aligned,
    )
