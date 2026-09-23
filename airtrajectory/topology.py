from dataclasses import dataclass, field
from typing import Dict, Iterable, Literal


@dataclass(frozen=True)
class ZoneNode:
    id: str
    volume_m3: float
    kind: str = "room"


@dataclass(frozen=True)
class OpeningEdge:
    id: str
    source: str
    target: str
    kind: Literal["window", "door", "vent"]
    max_area_m2: float
    controllable: bool = True


@dataclass
class BuildingTopology:
    zones: Dict[str, ZoneNode] = field(default_factory=dict)
    openings: Dict[str, OpeningEdge] = field(default_factory=dict)
    outside_id: str = "OUTSIDE"

    @classmethod
    def from_parts(cls, zones: Iterable[ZoneNode], openings: Iterable[OpeningEdge]):
        model = cls(
            zones={z.id: z for z in zones},
            openings={o.id: o for o in openings},
        )
        model.validate()
        return model

    def validate(self) -> None:
        valid_nodes = set(self.zones) | {self.outside_id}
        if not self.zones:
            raise ValueError("topology requires at least one zone")
        for edge in self.openings.values():
            if edge.source not in valid_nodes or edge.target not in valid_nodes:
                raise ValueError(f"opening {edge.id} references an unknown node")
            if edge.source == edge.target:
                raise ValueError(f"opening {edge.id} cannot connect a node to itself")
            if edge.max_area_m2 <= 0:
                raise ValueError(f"opening {edge.id} max_area_m2 must be positive")

    def controllable_openings(self) -> list[str]:
        return [e.id for e in self.openings.values() if e.controllable]
