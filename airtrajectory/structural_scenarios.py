"""Deterministic non-chain topology fixtures for learning *plumbing* holdouts.

Graph structures are toy test families. They are not floorplan geometry,
CONTAM PRJ models, calibrated airflow or a substitute for field validation.
"""
from __future__ import annotations

import random

from .scenario import VentilationScenario, generate_chain_scenario
from .topology import BuildingTopology, OpeningEdge, ZoneNode


_FAMILY_DOORS = {
    "branch": ((0, 1), (1, 2), (1, 3), (3, 4)),
    "hub": ((0, 1), (0, 2), (0, 3), (0, 4)),
    "loop": ((0, 1), (1, 2), (2, 3), (3, 4), (4, 0)),
    "irregular": ((0, 1), (1, 2), (1, 3), (3, 4), (4, 0)),
}


def generate_structural_scenario(seed: int, family: str) -> VentilationScenario:
    """Return a five-room scenario with a declared, inspectable graph family."""
    if family == "chain":
        return generate_chain_scenario(seed, rooms=5)
    if family not in _FAMILY_DOORS:
        raise ValueError(f"unsupported topology family: {family}")
    rng = random.Random(seed)
    zones = [
        ZoneNode(f"room{i + 1}", rng.uniform(24, 55))
        for i in range(5)
    ]
    openings = [
        OpeningEdge(
            f"W{i + 1}", zone.id, "OUTSIDE", "window",
            rng.uniform(0.8, 1.6),
        )
        for i, zone in enumerate(zones)
    ]
    openings.extend(
        OpeningEdge(
            f"D{i + 1}", zones[source].id, zones[target].id, "door",
            rng.uniform(1.4, 2.0),
        )
        for i, (source, target) in enumerate(_FAMILY_DOORS[family])
    )
    topology = BuildingTopology.from_parts(zones, openings)
    return VentilationScenario(
        id=f"{family}-5-s{seed}",
        topology=topology,
        initial_co2={zone.id: rng.uniform(700, 1550) for zone in zones},
        occupancy={zone.id: rng.randint(0, 3) for zone in zones},
        rain=rng.random() < 0.2,
        outdoor_temp_c=rng.uniform(5, 34),
    )
