"""Compile semantic VentilationPath objects into joint control candidates.

The compiler keeps the semantic path as the source of truth:
- exterior openings on the path receive the requested intensity;
- all other controllable exterior openings are explicitly closed;
- internal openings are not rewritten here because the current real-CONTAM
  Golden Case holds internal doors at their origin state.

This module therefore bridges topology-derived path discovery into the existing
Independent-vs-Joint real-CONTAM evaluator without inventing a new simulator.
"""
from __future__ import annotations

from typing import Any, Iterable

from .ventilation_paths import discover_ventilation_paths


def _normalize_intensities(values: Iterable[float]) -> tuple[float, ...]:
    normalized = tuple(sorted({float(value) for value in values}))
    if not normalized:
        raise ValueError("at least one path intensity is required")
    if any(value < 0 or value > 100 for value in normalized):
        raise ValueError("path intensities must be within [0,100]")
    return normalized


def build_ventilation_path_joint_candidates(
    topology,
    *,
    intensities: Iterable[float] = (35.0, 55.0, 75.0),
    inactive_exterior_pct: float = 0.0,
) -> list[dict[str, Any]]:
    """Build Golden-Case joint candidates from topology-derived paths."""

    levels = _normalize_intensities(intensities)
    inactive = float(inactive_exterior_pct)
    if inactive < 0 or inactive > 100:
        raise ValueError("inactive_exterior_pct must be within [0,100]")

    exterior_ids = sorted(
        edge.id
        for edge in topology.openings.values()
        if edge.controllable
        and topology.outside_id in (edge.source, edge.target)
    )
    if len(exterior_ids) < 2:
        raise ValueError(
            "ventilation path candidates require at least two controllable exterior openings"
        )

    paths = discover_ventilation_paths(topology)
    if not paths:
        raise ValueError("topology has no discoverable ventilation paths")

    rows: list[dict[str, Any]] = []
    for path in paths:
        active = set(path.exterior_openings)
        for intensity in levels:
            opening_pct = {
                opening_id: (
                    intensity if opening_id in active else inactive
                )
                for opening_id in exterior_ids
            }
            rows.append(
                {
                    "label": (
                        f"ventpath:{path.exterior_openings[0]}"
                        f"->{path.exterior_openings[1]}@{intensity:g}"
                    ),
                    "opening_pct": opening_pct,
                    "ventilation_path": {
                        "id": path.id,
                        "opening_ids": list(path.opening_ids),
                        "zones": list(path.zones),
                        "max_bottleneck_area_m2": path.max_bottleneck_area_m2,
                    },
                    "intensity_pct": intensity,
                    "inactive_exterior_pct": inactive,
                }
            )
    return rows


def inject_ventilation_path_candidates(
    case: dict[str, Any],
    topology,
    *,
    intensities: Iterable[float] = (35.0, 55.0, 75.0),
    inactive_exterior_pct: float = 0.0,
) -> dict[str, Any]:
    """Return a Golden Case copy whose joint candidates come from topology."""

    if not isinstance(case, dict):
        raise ValueError("golden case must be an object")
    derived = build_ventilation_path_joint_candidates(
        topology,
        intensities=intensities,
        inactive_exterior_pct=inactive_exterior_pct,
    )
    payload = dict(case)
    payload["joint_candidates"] = [
        {
            "label": row["label"],
            "opening_pct": dict(row["opening_pct"]),
        }
        for row in derived
    ]
    payload["candidate_source"] = "topology-derived-ventilation-paths"
    payload["ventilation_path_candidates"] = derived
    return payload
