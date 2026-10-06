"""One-shot WindowPilot read-only capture → alignment → field validation."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .contam_field_capture import compile_field_capture_bundle
from .contam_field_validation import validate_contam_against_field
from .layout import LayoutContract
from .physical import PhysicalWindowDriver
from .windowpilot_field_capture import collect_windowpilot_field_capture
from .windowpilot_validation_preflight import (
    preflight_windowpilot_field_validation,
)
from .windowpilot_contract_baseline import (
    compare_windowpilot_contract_baseline,
)


def _sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def run_windowpilot_field_validation(
    *,
    layout: LayoutContract,
    config: dict[str, Any],
    drivers: Mapping[str, PhysicalWindowDriver],
    protocol: dict[str, Any],
    runtime_receipt: dict[str, Any],
    validation_id: str,
    sample_count: int | None = None,
    contract_baseline: dict[str, Any] | None = None,
    contract_probe_report: dict[str, Any] | None = None,
    sleep_fn=None,
    clock_fn=None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if (contract_baseline is None) != (contract_probe_report is None):
        raise ValueError(
            "contract_baseline and contract_probe_report must be supplied together"
        )

    contract_comparison = None
    if contract_baseline is not None:
        contract_comparison = compare_windowpilot_contract_baseline(
            baseline=contract_baseline,
            current_report=contract_probe_report,
        )
        if contract_comparison["status"] != "MATCH":
            raise RuntimeError(
                "WindowPilot contract baseline drift blocks field validation: "
                + json.dumps(
                    contract_comparison["drifts"],
                    sort_keys=True,
                )
            )

    capture_kwargs = {}
    if sleep_fn is not None:
        capture_kwargs["sleep_fn"] = sleep_fn
    if clock_fn is not None:
        capture_kwargs["clock_fn"] = clock_fn

    preflight_kwargs = {}
    if clock_fn is not None:
        preflight_kwargs["clock_fn"] = clock_fn
    preflight = preflight_windowpilot_field_validation(
        layout=layout,
        config=config,
        drivers=drivers,
        protocol=protocol,
        runtime_receipt=runtime_receipt,
        **preflight_kwargs,
    )

    capture = collect_windowpilot_field_capture(
        layout=layout,
        config=config,
        drivers=drivers,
        protocol=protocol,
        runtime_receipt=runtime_receipt,
        validation_id=validation_id,
        sample_count=sample_count,
        **capture_kwargs,
    )
    aligned = compile_field_capture_bundle(
        layout=layout,
        runtime_receipt=runtime_receipt,
        protocol=protocol,
        capture=capture,
    )
    validation = validate_contam_against_field(
        layout=layout,
        runtime_receipt=runtime_receipt,
        protocol=protocol,
        field_bundle=aligned,
    )

    payload = {
        "schema_version": "0.1",
        "pipeline": "windowpilot-field-validation-v1",
        "status": validation["status"],
        "topology_id": layout.topology_id,
        "runtime_receipt_sha256": runtime_receipt[
            "runtime_receipt_sha256"
        ],
        "protocol_sha256": validation["protocol_sha256"],
        "contract_baseline_sha256": (
            contract_baseline["baseline_sha256"]
            if contract_baseline is not None
            else None
        ),
        "contract_probe_receipt_sha256": (
            contract_probe_report["config_probe_receipt_sha256"]
            if contract_probe_report is not None
            else None
        ),
        "contract_comparison_sha256": (
            contract_comparison["comparison_sha256"]
            if contract_comparison is not None
            else None
        ),
        "preflight_receipt_sha256": preflight[
            "preflight_receipt_sha256"
        ],
        "windowpilot_capture_sha256": validation[
            "windowpilot_capture_sha256"
        ],
        "raw_capture_sha256": validation["raw_capture_sha256"],
        "alignment_sha256": validation["alignment_sha256"],
        "capture_bundle_sha256": _sha256(capture),
        "aligned_bundle_sha256": _sha256(aligned),
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
        capture,
        aligned,
    )
