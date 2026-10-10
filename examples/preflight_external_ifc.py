"""IfcOpenShell-backed evidence gate for an external IFC file.

Uses upstream IfcOpenShell geometry/space-boundary extraction and the existing
AirTrajectory strict importer. Never guesses missing walls, adjacency or volume.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

from airtrajectory.importers.ifc import inspect_ifc_control_readiness, import_ifc


def preflight(source: Path, output: Path) -> dict:
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    inspection = inspect_ifc_control_readiness(source)
    if inspection["source"]["sha256"] != source_hash:
        raise ValueError("IFC changed during inspection")
    result = {
        "schema_version": "0.1",
        "source_ifc_sha256": source_hash,
        "ifc_schema": inspection["source"]["schema"],
        "space_count": inspection["space_count"],
        "opening_count": inspection["opening_count"],
        "space_boundary_count": inspection["space_boundary_count"],
        "geometry_backend": "ifcopenshell",
        "blockers": inspection["blockers"],
        "status": inspection["status"],
        "layout_contract_sha256": None,
        "layout_file": None,
        "native_solver_executed": False,
        "engineering_truth": False,
    }
    if inspection["status"] == "READY":
        layout = import_ifc(source)
        if hashlib.sha256(source.read_bytes()).hexdigest() != source_hash:
            raise ValueError("IFC changed during import")
        if layout.source_provenance.get("source_sha256") != source_hash:
            raise ValueError("IFC importer source mismatch")
        # LayoutContract.to_dict is canonical and validates real source topology.
        layout_path = output.with_name(output.stem + ".layout.json")
        layout_path.parent.mkdir(parents=True, exist_ok=True)
        layout_path.write_text(json.dumps(layout.to_dict(), indent=2, sort_keys=True)+"\n", encoding="utf-8")
        result["layout_contract_sha256"] = layout.sha256()
        result["layout_file"] = str(layout_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ifc", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    result = preflight(args.ifc, args.out)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
