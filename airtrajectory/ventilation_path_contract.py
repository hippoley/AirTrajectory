"""Portable VentilationPath contract.

This is the semantic seam between an upstream building topology and downstream
physics/policy implementations. It deliberately carries no RL- or simulator-
specific state.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .layout import LayoutContract
from .ventilation_paths import discover_ventilation_paths


def _sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def build_ventilation_path_contract(layout: LayoutContract) -> dict[str, Any]:
    """Emit a deterministic language-neutral path-set receipt."""

    topology = layout.to_building_topology()
    paths = discover_ventilation_paths(topology)
    rows = [
        {
            "path_id": path.id,
            "exterior_openings": list(path.exterior_openings),
            "internal_openings": list(path.internal_openings),
            "opening_ids": list(path.opening_ids),
            "zones": list(path.zones),
            "max_bottleneck_area_m2": float(path.max_bottleneck_area_m2),
            "semantics": {
                "kind": "candidate-cross-ventilation-path",
                "directionality": "undirected-candidate",
                "effectiveness": "unverified",
            },
        }
        for path in paths
    ]
    core = {
        "schema_version": "0.1",
        "contract": "airtrajectory-ventilation-path-v0.1",
        "topology_id": layout.topology_id,
        "topology_sha256": layout.sha256(),
        "discovery": {
            "algorithm": "deterministic-shortest-internal-opening-path-v1",
            "physics_assumption": "connectivity-only",
        },
        "paths": rows,
        "evidence_boundary": (
            "candidate paths are derived from topology connectivity only; "
            "airflow direction/effectiveness requires a physics or field adapter"
        ),
    }
    return {**core, "contract_sha256": _sha256(core)}
