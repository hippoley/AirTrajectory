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


class ScenarioMultizoneEnvironment(ToyMultizoneEnvironment):
    """Episode environment with occupancy sources and weather context.

    Still a toy/surrogate backend: useful for learning plumbing and transfer tests,
    not engineering airflow truth.
    """
    def __init__(self, scenario, dt_minutes: float = 1.0, horizon_steps: int = 120, judge=None):
        from .judge import VentilationJudge
        super().__init__(
            scenario.topology,
            initial_co2=scenario.initial_co2,
            outdoor_co2=scenario.outdoor_co2,
            dt_minutes=dt_minutes,
            horizon_steps=horizon_steps,
        )
        self.scenario=scenario
        self.occupancy=dict(scenario.occupancy)
        self.rain=bool(scenario.rain)
        self.outdoor_temp_c=float(scenario.outdoor_temp_c)
        self.judge=judge or VentilationJudge()

    def _observation(self):
        obs=super()._observation()
        exterior=[
            e for e in self.topology.openings.values()
            if e.source==self.topology.outside_id or e.target==self.topology.outside_id
        ]
        obs.update({
            "occupancy":deepcopy(self.occupancy),
            "rain":self.rain,
            "outdoor_temp_c":self.outdoor_temp_c,
            "exterior_openings":[e.id for e in exterior],
            "opening_zone":{
                e.id:(e.target if e.source==self.topology.outside_id else e.source)
                for e in exterior
            },
            "interior_openings":[
                e.id for e in self.topology.openings.values()
                if e.id not in {x.id for x in exterior}
            ],
        })
        return obs

    def reset(self, seed=None):
        obs,info=super().reset(seed)
        info.update({
            "scenario_id":self.scenario.id,
            "backend":"toy-scenario-v1",
            "physics_fidelity":"toy",
        })
        return obs,info

    def step(self, actions):
        actions=list(actions)
        observation=self._observation()
        previous_openings=deepcopy(self.openings)

        # Explicit occupant source term. This is a learning surrogate, not a
        # calibrated metabolic/airflow model.
        for zone_id,people in self.occupancy.items():
            volume=self.topology.zones[zone_id].volume_m3
            self.co2[zone_id] += float(people) * 18.0 * (30.0/volume) * self.dt_minutes

        next_observation,_,terminated,truncated,info=super().step(actions)
        reward=self.judge.score(observation,next_observation,actions,previous_openings)
        info.update({"backend":"toy-scenario-v1","physics_fidelity":"toy"})
        return next_observation,reward,terminated,truncated,info
