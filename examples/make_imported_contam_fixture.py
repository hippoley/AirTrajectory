"""Construct a synthetic imported-layout *integration fixture* with profiles.

Not an independently supplied unfamiliar home or engineering validated geometry.
Purpose: check whether imported-floorplan routes to the native ContamX runner.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from airtrajectory.contam_profile import illustrative_opening_profile
from airtrajectory.layout import LayoutContract

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def save(path, obj):
    path.write_text(json.dumps(obj, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def build(destination: Path):
    destination.mkdir(parents=True, exist_ok=True)
    layout = read("web/data/home_topology.fixed.json")
    layout["topology_id"] = "synthetic.imported-smoke.v1"
    layout["source_kind"] = "imported-floorplan"
    layout["capabilities"]["arbitrary_topology_import"] = "supported"
    layout["capabilities"]["floorplan_geometry_editable"] = True
    layout["source_provenance"] = {
        "format": "synthetic-json",
        "source_sha256": hashlib.sha256(b"airtrajectory-synthetic-import-smoke-v1").hexdigest(),
        "importer": {"id": "airtrajectory-integration-fixture", "version": "1"},
        "evidence_level": "synthetic-derived-from-fixed-demo",
    }
    layout["rooms"][0]["volume_m3"] = 78.0
    layout["openings"][0]["position_t"] = 0.42
    layout["openings"][1]["position_t"] = 0.61
    metric = read("examples/contam_metric_geometry.example.json")
    metric["topology_id"] = layout["topology_id"]
    metric["layout_contract_sha256"] = LayoutContract.from_dict(layout).sha256()
    metric["profile_id"] = "synthetic-import-metric"
    boundary = read("examples/contam_boundary_profile.example.json")
    boundary["profile_id"] = "synthetic-import-boundary"
    prj = read("examples/contam_prj_profile.example.json")
    prj["profile_id"] = "synthetic-import-prj"
    airflow = illustrative_opening_profile()
    airflow["profile_id"] = "synthetic-import-airflow"
    files = {
        "layout.json": layout,
        "metric.json": metric,
        "boundary.json": boundary,
        "prj.json": prj,
        "airflow.json": airflow,
    }
    for name, payload in files.items():
        save(destination / name, payload)
    return destination


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=ROOT / "artifacts" / "imported-smoke")
    args = parser.parse_args()
    print(build(args.out_dir))
