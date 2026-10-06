"""Topology-derived candidate ventilation paths.

A VentilationPath is a semantic control object that connects two exterior
openings through zero or more internal openings.  Discovery is deterministic
and depends only on BuildingTopology, so downstream CONTAM/CFD/trajectory
systems can share the same path identity without hard-coded window IDs.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .topology import BuildingTopology, OpeningEdge


@dataclass(frozen=True)
class VentilationPath:
    id: str
    exterior_openings: tuple[str, str]
    internal_openings: tuple[str, ...]
    zones: tuple[str, ...]
    max_bottleneck_area_m2: float

    @property
    def opening_ids(self) -> tuple[str, ...]:
        return (
            self.exterior_openings[0],
            *self.internal_openings,
            self.exterior_openings[1],
        )

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "exterior_openings": list(self.exterior_openings),
            "internal_openings": list(self.internal_openings),
            "zones": list(self.zones),
            "opening_ids": list(self.opening_ids),
            "max_bottleneck_area_m2": self.max_bottleneck_area_m2,
        }


def _zone_for_exterior(
    topology: BuildingTopology,
    edge: OpeningEdge,
) -> str:
    if edge.source == topology.outside_id:
        return edge.target
    if edge.target == topology.outside_id:
        return edge.source
    raise ValueError(f"opening {edge.id} is not exterior")


def _internal_adjacency(
    topology: BuildingTopology,
) -> dict[str, list[tuple[str, OpeningEdge]]]:
    adjacency = {zone_id: [] for zone_id in topology.zones}
    for edge in topology.openings.values():
        if topology.outside_id in (edge.source, edge.target):
            continue
        adjacency[edge.source].append((edge.target, edge))
        adjacency[edge.target].append((edge.source, edge))
    for rows in adjacency.values():
        rows.sort(key=lambda item: (item[0], item[1].id))
    return adjacency


def _shortest_internal_path(
    topology: BuildingTopology,
    start: str,
    goal: str,
) -> tuple[tuple[str, ...], tuple[str, ...]] | None:
    """Return deterministic shortest zone/opening path between two zones."""

    if start == goal:
        return ((start,), ())

    adjacency = _internal_adjacency(topology)
    queue: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [
        (start, (start,), ())
    ]
    visited = {start}

    while queue:
        zone, zones, openings = queue.pop(0)
        for neighbor, edge in adjacency.get(zone, []):
            if neighbor in visited:
                continue
            next_zones = (*zones, neighbor)
            next_openings = (*openings, edge.id)
            if neighbor == goal:
                return next_zones, next_openings
            visited.add(neighbor)
            queue.append((neighbor, next_zones, next_openings))
    return None


def discover_ventilation_paths(
    topology: BuildingTopology,
) -> list[VentilationPath]:
    """Discover deterministic cross-ventilation candidates.

    Each candidate starts and ends at distinct exterior openings and connects
    their adjacent zones through the shortest available internal-opening path.
    Pairs with no internal connectivity are omitted.
    """

    topology.validate()
    exterior = [
        edge
        for edge in topology.openings.values()
        if topology.outside_id in (edge.source, edge.target)
    ]
    exterior.sort(key=lambda edge: edge.id)

    paths: list[VentilationPath] = []
    for i, left in enumerate(exterior):
        left_zone = _zone_for_exterior(topology, left)
        for right in exterior[i + 1 :]:
            right_zone = _zone_for_exterior(topology, right)
            if left_zone == right_zone:
                # Same-zone two-opening candidates can still provide useful
                # single-zone cross ventilation without an internal opening.
                zones = (left_zone,)
                internal_ids: tuple[str, ...] = ()
            else:
                resolved = _shortest_internal_path(
                    topology,
                    left_zone,
                    right_zone,
                )
                if resolved is None:
                    continue
                zones, internal_ids = resolved

            edge_ids = (left.id, *internal_ids, right.id)
            areas = [
                topology.openings[opening_id].max_area_m2
                for opening_id in edge_ids
            ]
            canonical = "-".join(edge_ids)
            paths.append(
                VentilationPath(
                    id=f"path:{canonical}",
                    exterior_openings=(left.id, right.id),
                    internal_openings=internal_ids,
                    zones=zones,
                    max_bottleneck_area_m2=min(areas),
                )
            )

    return paths
