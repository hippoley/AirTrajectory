"""Import gateway/logger field records from JSONL or CSV.

This adapter keeps transport/file concerns outside the alignment algorithm. It
assembles the same raw capture contract consumed by contam_field_capture and
binds the source files with SHA-256 provenance.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any


_REQUIRED_RECORD_FIELDS = (
    "timestamp",
    "signal_type",
    "target_id",
    "value",
    "unit",
    "quality",
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_bytes(path: str | Path) -> bytes:
    return Path(path).read_bytes()


def _normalize_record(row: dict[str, Any], *, index: int) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError(f"record {index} must be an object")
    missing = [
        field
        for field in _REQUIRED_RECORD_FIELDS
        if row.get(field) is None or str(row.get(field)) == ""
    ]
    if missing:
        raise ValueError(
            f"record {index} missing fields: " + ",".join(missing)
        )
    return {
        "timestamp": str(row["timestamp"]),
        "signal_type": str(row["signal_type"]),
        "target_id": str(row["target_id"]),
        "value": float(row["value"]),
        "unit": str(row["unit"]),
        "quality": str(row["quality"]),
    }


def load_jsonl_records(data: bytes) -> list[dict[str, Any]]:
    text = data.decode("utf-8-sig")
    records = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"invalid JSONL at line {line_number}: {exc.msg}"
            ) from exc
        records.append(_normalize_record(row, index=line_number))
    if not records:
        raise ValueError("JSONL capture contains no records")
    return records


def load_csv_records(data: bytes) -> list[dict[str, Any]]:
    text = data.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("CSV capture has no header")
    missing_headers = [
        field for field in _REQUIRED_RECORD_FIELDS
        if field not in reader.fieldnames
    ]
    if missing_headers:
        raise ValueError(
            "CSV capture missing headers: " + ",".join(missing_headers)
        )
    records = [
        _normalize_record(row, index=index)
        for index, row in enumerate(reader, start=2)
        if any(str(value or "").strip() for value in row.values())
    ]
    if not records:
        raise ValueError("CSV capture contains no records")
    return records


def import_field_capture(
    *,
    manifest_path: str | Path,
    records_path: str | Path,
    records_format: str = "auto",
) -> dict[str, Any]:
    manifest_bytes = _read_bytes(manifest_path)
    records_bytes = _read_bytes(records_path)
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError("field capture manifest is not valid JSON") from exc
    if not isinstance(manifest, dict):
        raise ValueError("field capture manifest must be an object")
    if "records" in manifest:
        raise ValueError(
            "field capture manifest must not embed records when using an importer"
        )

    fmt = str(records_format or "auto").lower()
    if fmt == "auto":
        suffix = Path(records_path).suffix.lower()
        if suffix in (".jsonl", ".ndjson"):
            fmt = "jsonl"
        elif suffix == ".csv":
            fmt = "csv"
        else:
            raise ValueError(
                "cannot infer record format; use jsonl or csv explicitly"
            )
    if fmt == "jsonl":
        records = load_jsonl_records(records_bytes)
    elif fmt == "csv":
        records = load_csv_records(records_bytes)
    else:
        raise ValueError("records_format must be auto, jsonl, or csv")

    source_records_path = Path(records_path)
    source_manifest_path = Path(manifest_path)
    import_payload = {
        "adapter": "field-capture-importer-v1",
        "records_format": fmt,
        "manifest_filename": source_manifest_path.name,
        "manifest_sha256": _sha256_bytes(manifest_bytes),
        "records_filename": source_records_path.name,
        "records_sha256": _sha256_bytes(records_bytes),
        "record_count": len(records),
    }
    import_receipt_sha256 = hashlib.sha256(
        json.dumps(
            import_payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        **manifest,
        "records": records,
        "import_provenance": {
            **import_payload,
            "import_receipt_sha256": import_receipt_sha256,
        },
    }
