"""Independent product gate: external IFC source must survive native solve and scoring.

This checker cannot create or substitute missing evidence. It fails closed and
only accepts matching input identity and proof levels.
"""
import argparse
import hashlib
import json
from pathlib import Path


def _sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def verify(layout, native, scoring, source_bytes):
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    provenance = layout.get("source_provenance") or {}
    if layout.get("source_kind") != "imported-floorplan" or provenance.get("format", "").upper() != "IFC":
        raise ValueError("external acceptance requires imported IFC source")
    if provenance.get("source_sha256") != source_hash:
        raise ValueError("IFC source bytes do not match imported layout provenance")
    if provenance.get("geometry_fidelity") in (None, "", "synthetic", "illustrative"):
        raise ValueError("IFC geometry provenance unavailable")
    if not isinstance(native, dict) or not isinstance(scoring, dict):
        raise ValueError("native and scoring receipts must be objects")
    # A matching SHA field alone is not a verified receipt: recompute its
    # canonical digest and reject changed outputs even when source IDs match.
    native_payload = dict(native)
    signed_native = native_payload.pop("receipt_sha256", None)
    if signed_native != _sha(native_payload):
        raise ValueError("native receipt SHA-256 integrity check failed")
    scoring_payload = dict(scoring)
    signed_scoring = scoring_payload.pop("receipt_sha256", None)
    if signed_scoring != _sha(scoring_payload):
        raise ValueError("scoring receipt SHA-256 integrity check failed")
    if native.get("marker") != "IMPORTED_CONTAM_NATIVE_EXECUTED":
        raise ValueError("native solver execution receipt missing")
    if native.get("topology_id") != layout.get("topology_id"):
        raise ValueError("native topology differs from source IFC")
    if native.get("source_ifc_sha256") != source_hash:
        raise ValueError("native receipt not bound to exact IFC source")
    if scoring.get("source_ifc_sha256") != source_hash:
        raise ValueError("strategy scoring not bound to exact IFC source")
    if scoring.get("native_receipt_sha256") != native.get("receipt_sha256"):
        raise ValueError("strategy scoring references a different solver result")
    if scoring.get("status") != "NATIVE_CONTAM_SCORED":
        raise ValueError("missing native solver strategy scoring")
    if native.get("engineering_truth") is True and not native.get("engineering_validation_receipt_sha256"):
        raise ValueError("unsubstantiated engineering validation claim")
    receipt = {
        "status": "EXTERNAL_IFC_CHAIN_EVIDENCE_PRESENT",
        "source_ifc_sha256": source_hash,
        "native_receipt_sha256": native["receipt_sha256"],
        "scoring_receipt_sha256": scoring.get("receipt_sha256"),
        "independent_replay_verified": False,
        "product_verified_closed": False,
        "evidence_boundary": "Presence and identity checks only; solver fidelity and independent replay require external attestation.",
    }
    return {**receipt, "verification_sha256": _sha(receipt)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ifc", required=True, type=Path)
    parser.add_argument("--layout", required=True, type=Path)
    parser.add_argument("--native", required=True, type=Path)
    parser.add_argument("--scoring", required=True, type=Path)
    args = parser.parse_args()
    result = verify(
        json.loads(args.layout.read_text(encoding="utf-8")),
        json.loads(args.native.read_text(encoding="utf-8")),
        json.loads(args.scoring.read_text(encoding="utf-8")),
        args.ifc.read_bytes(),
    )
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
