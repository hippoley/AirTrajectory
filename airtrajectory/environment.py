from abc import ABC, abstractmethod
from copy import deepcopy
from typing import Any, Dict, Iterable

from .topology import BuildingTopology
from .trajectory import RewardVector, TransitionAction


class VentilationEnvironment(ABC):
    @abstractmethod
    def reset(self, seed: int | None = None) -> tuple[Dict[str, Any], Dict[str, Any]]:
        ...

    @abstractmethod
    def step(self, actions: Iterable[TransitionAction]):
        """Return observation, reward vector, terminated, truncated, info."""
        ...


class SnapshotableEnvironment(VentilationEnvironment):
    @abstractmethod
    def snapshot(self) -> Dict[str, Any]:
        ...

    @abstractmethod
    def restore(self, snapshot: Dict[str, Any]) -> None:
        ...


class ToyMultizoneEnvironment(SnapshotableEnvironment):
    """Deterministic topology-aware CO2 mixing baseline.

    This validates trajectory plumbing and branching semantics only.
    It is not an engineering airflow solver.
    """

    def __init__(
        self,
        topology: BuildingTopology,
        initial_co2=None,
        outdoor_co2: float = 420.0,
        dt_minutes: float = 1.0,
        horizon_steps: int = 60,
    ):
        self.topology = topology
        self.initial_co2 = initial_co2 or {z: 1200.0 for z in topology.zones}
        self.outdoor_co2 = outdoor_co2
        self.dt_minutes = dt_minutes
        self.horizon_steps = horizon_steps
        self._step = 0
        self.co2 = {}
        self.openings = {}

    def _observation(self):
        return {
            "step": self._step,
            "co2_ppm": deepcopy(self.co2),
            "opening_pct": deepcopy(self.openings),
            "outdoor_co2_ppm": self.outdoor_co2,
        }

    def reset(self, seed=None):
        self._step = 0
        self.co2 = deepcopy(self.initial_co2)
        self.openings = {o: 0.0 for o in self.topology.openings}
        return self._observation(), {"backend": "toy-multizone-v1"}

    def snapshot(self):
        return {
            "step": self._step,
            "co2": deepcopy(self.co2),
            "openings": deepcopy(self.openings),
        }

    def restore(self, snapshot):
        self._step = int(snapshot["step"])
        self.co2 = deepcopy(snapshot["co2"])
        self.openings = deepcopy(snapshot["openings"])

    def step(self, actions):
        previous_openings = deepcopy(self.openings)
        for action in actions:
            if action.opening_id not in self.openings:
                raise KeyError(f"unknown opening: {action.opening_id}")
            self.openings[action.opening_id] = action.target_pct

        old = deepcopy(self.co2)
        next_co2 = deepcopy(old)

        for edge in self.topology.openings.values():
            fraction = self.openings[edge.id] / 100.0
            if fraction <= 0:
                continue
            rate_per_minute = 0.02 + 0.12 * fraction * edge.max_area_m2
            rate = min(0.95, rate_per_minute * self.dt_minutes)
            if edge.source == self.topology.outside_id or edge.target == self.topology.outside_id:
                zone = edge.target if edge.source == self.topology.outside_id else edge.source
                next_co2[zone] += (self.outdoor_co2 - old[zone]) * rate
            else:
                delta = (old[edge.target] - old[edge.source]) * rate
                next_co2[edge.source] += delta
                next_co2[edge.target] -= delta

        self.co2 = {z: max(self.outdoor_co2, value) for z, value in next_co2.items()}
        self._step += 1
        iaq_penalty = -sum(max(0.0, value - 800.0) / 400.0 for value in self.co2.values())
        wear = -sum(abs(self.openings[k] - previous_openings[k]) / 100.0 for k in self.openings)
        reward = RewardVector(iaq=iaq_penalty, actuator_wear=wear)
        terminated = self._step >= self.horizon_steps
        return self._observation(), reward, terminated, False, {"backend": "toy-multizone-v1"}
