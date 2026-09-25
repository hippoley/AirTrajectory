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
