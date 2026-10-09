from dataclasses import dataclass, field
from math import isfinite
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
        # A dict comprehension silently overwrites duplicate IDs. In a
        # physical topology that can rebind a sensor or actuator to a
        # different room, so reject collisions before constructing the map.
        zone_map: Dict[str, ZoneNode] = {}
        opening_map: Dict[str, OpeningEdge] = {}
        for zone in zones:
            if zone.id in zone_map:
                raise ValueError(f"duplicate zone id: {zone.id}")
            zone_map[zone.id] = zone
        for opening in openings:
            if opening.id in opening_map:
                raise ValueError(f"duplicate opening id: {opening.id}")
            opening_map[opening.id] = opening
        model = cls(zones=zone_map, openings=opening_map)
        model.validate()
        return model

    def validate(self) -> None:
        valid_nodes = set(self.zones) | {self.outside_id}
        if not self.zones:
            raise ValueError("topology requires at least one zone")
        if not isinstance(self.outside_id, str) or not self.outside_id or self.outside_id in self.zones:
            raise ValueError("outside_id must be distinct from room IDs")
        for key, zone in self.zones.items():
            if not isinstance(key, str) or not key or key != zone.id:
                raise ValueError("zone dictionary key/id mismatch")
            if not isinstance(zone.volume_m3, (int, float)) or not isfinite(zone.volume_m3) or zone.volume_m3 <= 0:
                raise ValueError(f"zone {key} volume_m3 must be finite and positive")
        for key, edge in self.openings.items():
            if not isinstance(key, str) or not key or key != edge.id:
                raise ValueError("opening dictionary key/id mismatch")
            if edge.kind not in {"window", "door", "vent"}:
                raise ValueError(f"opening {key} has unsupported kind")
            if edge.source not in valid_nodes or edge.target not in valid_nodes:
                raise ValueError(f"opening {edge.id} references an unknown node")
            if edge.source == edge.target:
                raise ValueError(f"opening {edge.id} cannot connect a node to itself")
            if not isinstance(edge.max_area_m2, (int, float)) or not isfinite(edge.max_area_m2) or edge.max_area_m2 <= 0:
                raise ValueError(f"opening {edge.id} max_area_m2 must be finite and positive")

    def controllable_openings(self) -> list[str]:
        return [e.id for e in self.openings.values() if e.controllable]
