"""Native imported-layout ContamX smoke and browser-facing receipt.

This runner must be invoked on Windows with the official contamxpy runtime.
It never synthesizes numerical outputs, nor promotes illustrative inputs to
engineering truth.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
from airtrajectory.contam import ContamXSession


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_receipt(prj: Path, provenance_path: Path) -> dict:
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    if provenance.get("topology_id") == "demo.fixed-three-room.v1":
        raise ValueError("imported solver acceptance must not use fixed demo topology")
    zone_numbers = provenance["zone_numbers"]
    path_numbers = provenance["path_numbers"]
    controls = provenance["initial_input_controls"]
    if not zone_numbers or not path_numbers:
        raise ValueError("missing topology-specific zone/path mappings")
    if any(not str(key).startswith("zone:") for key in zone_numbers):
        raise ValueError("invalid zone identity mapping")
    if any(not str(key).startswith("path:") for key in path_numbers):
        raise ValueError("invalid path identity mapping")
    session = ContamXSession(
        str(prj), ambient=dict(provenance.get("contam_ambient") or {}),
        initial_input_controls={int(index): dict(spec) for index, spec in controls.items()},
    )
    try:
        meta = session.setup()
        if int(meta["zones"]) != len(zone_numbers) or int(meta["paths"]) != len(path_numbers):
            raise ValueError("native solver count mismatch with imported topology")
        expected_names = set(provenance["input_control_names"].values())
        if set(meta.get("input_control_names") or []) != expected_names:
            raise ValueError("native input controls mismatch with imported topology")
        session.step()
        flows = {key: float(session.path_flow(int(number)))
                 for key, number in sorted(path_numbers.items())}
        mass = {key: float(session.zone_mass_fraction(int(number), 0))
                for key, number in sorted(zone_numbers.items())}
        if not all(math.isfinite(v) for v in (*flows.values(), *mass.values())):
            raise ValueError("native solver returned non-finite values")
        if not any(abs(v) > 1e-12 for v in mass.values()):
            raise ValueError("native solver returned no non-zero zone contaminant state")
        if not any(abs(v) > 1e-12 for v in flows.values()):
            raise ValueError("native solver returned no non-zero path flow")
        payload = {
            "schema_version": "0.1",
            "marker": "IMPORTED_CONTAM_NATIVE_EXECUTED",
            "evidence_level": "NATIVE_CONTAM_ILLUSTRATIVE_INPUTS_NOT_FIELD",
            "execution_authorized": False,
            "topology_id": provenance["topology_id"],
            "layout_contract_sha256": provenance["layout_contract_sha256"],
            "source_ifc_sha256": (provenance.get("source_provenance") or {}).get("source_sha256") if str((provenance.get("source_provenance") or {}).get("format", "")).upper() == "IFC" else None,
            "prj_sha256": digest(prj),
            "generator_provenance_sha256": digest(provenance_path),
            "solver_version": meta.get("version"),
            "zone_count": int(meta["zones"]),
            "path_count": int(meta["paths"]),
            "input_control_names": sorted(expected_names),
            "path_flow_kg_s": flows,
            "zone_mass_fraction": mass,
            "engineering_truth": False,
            "source": "native-contamxpy-session",
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return {**payload, "receipt_sha256": hashlib.sha256(canonical.encode()).hexdigest()}
    finally:
        if session.started:
            session.close()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("prj", type=Path)
    p.add_argument("--provenance", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    receipt = native_receipt(args.prj, args.provenance)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    print(receipt["marker"], receipt["receipt_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
