from dataclasses import dataclass
from math import cos, hypot, radians, sin
from typing import Iterable

from .topology import BuildingTopology


@dataclass(frozen=True)
class FlowVector:
    x: float
    y: float
    vx: float
    vy: float
    speed: float


@dataclass(frozen=True)
class FlowField:
    backend: str
    wind_direction_deg: float
    wind_speed_mps: float
    vectors: tuple[FlowVector, ...]


class FastFlowField:
    """Cheap qualitative vector field for UI and rollout diagnostics.

    This is deliberately not CFD. It turns topology/opening state plus outdoor
    wind into a deterministic vector field with stable semantics that can later
    be replaced by CONTAM-derived or CFD-derived fields.
    """

    def __init__(self, topology: BuildingTopology):
        self.topology = topology

    def sample(
        self,
        points: Iterable[tuple[float, float]],
        opening_pct: dict[str, float],
        wind_direction_deg: float,
        wind_speed_mps: float,
    ) -> FlowField:
        angle = radians((wind_direction_deg + 180.0) % 360.0)
        wind_x = cos(angle) * max(0.0, wind_speed_mps) * 0.12
        wind_y = sin(angle) * max(0.0, wind_speed_mps) * 0.12
        controllable = list(self.topology.openings.values())
        vectors = []

        for x, y in points:
            vx, vy = wind_x, wind_y
            # Geometry-free topology attraction term. Coordinates are supplied
            # by the visual/layout adapter; backend-specific geometry will
            # replace this term when available.
            for index, edge in enumerate(controllable):
                fraction = max(0.0, min(100.0, opening_pct.get(edge.id, 0.0))) / 100.0
                phase = (index + 1) * 0.73
                strength = fraction * edge.max_area_m2 * 0.045
                vx += cos(phase + y * 0.01) * strength
                vy += sin(phase + x * 0.01) * strength

            speed = hypot(vx, vy)
            vectors.append(FlowVector(x=x, y=y, vx=vx, vy=vy, speed=speed))

        return FlowField(
            backend="fast-field-v1",
            wind_direction_deg=wind_direction_deg,
            wind_speed_mps=wind_speed_mps,
            vectors=tuple(vectors),
        )
