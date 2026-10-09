"""Scenario generation for topology-conditioned ventilation experiments."""
from dataclasses import dataclass
import random
from typing import Dict
from .topology import BuildingTopology, ZoneNode, OpeningEdge

@dataclass(frozen=True)
class VentilationScenario:
    id: str
    topology: BuildingTopology
    initial_co2: Dict[str,float]
    occupancy: Dict[str,int]
    rain: bool
    outdoor_co2: float=420.0
    outdoor_temp_c: float=20.0

def generate_chain_scenario(seed:int, rooms:int=3)->VentilationScenario:
    if rooms < 2: raise ValueError("rooms must be >= 2")
    rng=random.Random(seed)
    zones=[ZoneNode(f"room{i+1}",rng.uniform(24,55)) for i in range(rooms)]
    openings=[]
    for i,z in enumerate(zones):
        openings.append(OpeningEdge(f"W{i+1}",z.id,"OUTSIDE","window",rng.uniform(.8,1.6)))
    for i in range(rooms-1):
        openings.append(OpeningEdge(f"D{i+1}",zones[i].id,zones[i+1].id,"door",rng.uniform(1.4,2.0)))
    topo=BuildingTopology.from_parts(zones,openings)
    initial={z.id:rng.uniform(700,1550) for z in zones}
    occupancy={z.id:rng.randint(0,3) for z in zones}
    return VentilationScenario(
        id=f"chain-{rooms}-s{seed}",topology=topo,initial_co2=initial,occupancy=occupancy,
        rain=rng.random()<.2,outdoor_temp_c=rng.uniform(5,34)
    )


def topology_manifest(topology: BuildingTopology) -> dict:
    """Stable JSON-safe topology used by the Episode Lab and benchmark artifacts."""
    return {
        "outside_id": topology.outside_id,
        "zones": [
            {"id": z.id, "volume_m3": z.volume_m3}
            for z in topology.zones.values()
        ],
        "openings": [
            {
                "id": e.id,
                "source": e.source,
                "target": e.target,
                "kind": e.kind,
                "max_area_m2": e.max_area_m2,
                "controllable": e.controllable,
            }
            for e in topology.openings.values()
        ],
    }


def generate_structured_scenario(seed: int, rooms: int = 5, family: str = "hub") -> VentilationScenario:
    """Generate held-out non-chain graph families using deterministic local randomness.

    Internal door graph families: hub (star), loop (cycle), branch (fork).
    This is a toy simulation fixture, never imported-building/CONTAM evidence.
    """
    if rooms < 5:
        raise ValueError("structured benchmark requires at least five rooms")
    if family not in {"hub", "loop", "branch"}:
        raise ValueError("unsupported topology family")
    rng = random.Random(seed)
    zones = [ZoneNode(f"room{i+1}", rng.uniform(24, 55)) for i in range(rooms)]
    openings = [
        OpeningEdge(f"W{i+1}", z.id, "OUTSIDE", "window", rng.uniform(.8, 1.6))
        for i, z in enumerate(zones)
    ]
    if family == "hub":
        edges = [(0, i) for i in range(1, rooms)]
    elif family == "loop":
        edges = [(i, i+1) for i in range(rooms-1)] + [(rooms-1, 0)]
    else:
        edges = [(0, 1), (0, 2), (0, 3)] + [(i-1, i) for i in range(4, rooms)]
    for i, (a, z) in enumerate(edges):
        openings.append(OpeningEdge(f"D{i+1}", zones[a].id, zones[z].id,
                                    "door", rng.uniform(1.4, 2.0)))
    topology = BuildingTopology.from_parts(zones, openings)
    return VentilationScenario(
        id=f"{family}-{rooms}-s{seed}", topology=topology,
        initial_co2={z.id: rng.uniform(700, 1550) for z in zones},
        occupancy={z.id: rng.randint(0, 3) for z in zones},
        rain=rng.random() < .2, outdoor_temp_c=rng.uniform(5, 34),
    )
