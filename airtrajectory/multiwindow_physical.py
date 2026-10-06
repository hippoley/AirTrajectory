"""Multi-opening physical execution bus for the ventilation demo.

Each real opening is mapped to its own PhysicalWindowDriver (typically a
WindowPilotHTTPDriver). Internal doors or non-actuated openings may remain as
fixed topology state, but cannot be mistaken for measured hardware.

The bus fails closed when any commanded real opening is not physically
write-ready.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Mapping

from .physical import PhysicalWindowDriver
from .trajectory import ActuatorFeedback, RewardVector, TransitionAction


class MultiWindowPhysicalEnvironment:
    def __init__(
        self,
        topology,
        drivers: Mapping[str, PhysicalWindowDriver],
        *,
        fixed_openings: Mapping[str, float] | None = None,
        initial_openings: Mapping[str, float] | None = None,
        require_write_ready: bool = True,
    ):
        self.topology = topology
        self.drivers = dict(drivers)
        self.fixed_openings = {
            key: float(value)
            for key, value in (fixed_openings or {}).items()
        }
        self.openings = {
            opening_id: float((initial_openings or {}).get(opening_id, 0.0))
            for opening_id in topology.openings
        }
        self.openings.update(self.fixed_openings)
        self.require_write_ready = bool(require_write_ready)
        self.last_feedback: dict[str, ActuatorFeedback] = {}

        unknown = set(self.drivers) - set(topology.openings)
        if unknown:
            raise ValueError(
                "physical drivers reference unknown openings: "
                + ",".join(sorted(unknown))
            )
        overlap = set(self.drivers) & set(self.fixed_openings)
        if overlap:
            raise ValueError(
                "opening cannot be both physical and fixed: "
                + ",".join(sorted(overlap))
            )

    def _zone_for_opening(self, opening_id: str) -> str | None:
        edge = self.topology.openings[opening_id]
        if edge.source == self.topology.outside_id:
            return edge.target
        if edge.target == self.topology.outside_id:
            return edge.source
        return None

    def _readiness(self):
        result = {}
        for opening_id, driver in self.drivers.items():
            fn = getattr(driver, "physical_readiness", None)
            if fn is None:
                result[opening_id] = {
                    "physical_write_ready": False,
                    "write_blockers": ["driver has no physical_readiness contract"],
                }
                continue
            payload = fn()
            if not isinstance(payload, dict):
                raise RuntimeError(
                    f"{opening_id} physical readiness returned invalid payload"
                )
            result[opening_id] = payload
        return result

    def _assert_write_ready(self, opening_ids):
        readiness = self._readiness()
        blockers = []
        for opening_id in opening_ids:
            payload = readiness.get(opening_id) or {}
            if payload.get("physical_write_ready") is not True:
                reasons = payload.get("write_blockers") or ["not physical_write_ready"]
                blockers.append(
                    opening_id + ": " + "; ".join(str(x) for x in reasons)
                )
        if blockers:
            raise RuntimeError(
                "multi-window physical write blocked: " + " | ".join(blockers)
            )
        return readiness

    def _observe(self):
        co2_candidates: dict[str, list] = {}
        rain = False
        sensor_rows = []
        for opening_id, driver in self.drivers.items():
            zone = self._zone_for_opening(opening_id)
            for reading in driver.read_sensors():
                sensor_rows.append(reading)
                if reading.sensor_type == "co2" and zone is not None:
                    co2_candidates.setdefault(zone, []).append(reading)
                elif reading.sensor_type == "rain":
                    rain = rain or bool(reading.value)

        co2 = {}
        for zone, readings in co2_candidates.items():
            latest = max(readings, key=lambda item: item.timestamp)
            co2[zone] = latest.value

        return {
            "co2_ppm": co2,
            "rain": rain,
            "opening_pct": dict(self.openings),
            "sensor_readings": sensor_rows,
            "physical_openings": sorted(self.drivers),
            "fixed_openings": dict(self.fixed_openings),
        }

    def reset(self, seed=None):
        readiness = self._readiness()
        return self._observe(), {
            "backend": "multi-window-physical",
            "evidence_kind": "physical"
            if all(not d.capabilities().simulated for d in self.drivers.values())
            else "mixed-or-synthetic",
            "physical_opening_readiness": readiness,
            "driver_capabilities": {
                key: asdict(driver.capabilities())
                for key, driver in self.drivers.items()
            },
        }

    def step(self, actions):
        actions = list(actions)
        physical_actions = []
        for action in actions:
            if action.opening_id in self.drivers:
                physical_actions.append(action)
                continue
            if action.opening_id in self.fixed_openings:
                expected = self.fixed_openings[action.opening_id]
                if abs(float(action.target_pct) - expected) > 1e-9:
                    raise RuntimeError(
                        f"fixed opening {action.opening_id} cannot move "
                        f"from {expected:.1f}% to {float(action.target_pct):.1f}%"
                    )
                continue
            raise KeyError(f"opening {action.opening_id} has no physical driver")

        readiness = {}
        if physical_actions and self.require_write_ready:
            readiness = self._assert_write_ready(
                [action.opening_id for action in physical_actions]
            )

        feedback = []
        previous = dict(self.openings)
        for action in physical_actions:
            driver = self.drivers[action.opening_id]
            item = driver.set_position(action.opening_id, action.target_pct)
            feedback.append(item)
            self.last_feedback[action.opening_id] = item
            measured = (
                item.measured_position_pct
                if item.measured_position_pct is not None
                else item.estimated_position_pct
            )
            if measured is None:
                raise RuntimeError(
                    f"{action.opening_id} returned no actuator position feedback"
                )
            self.openings[action.opening_id] = float(measured)

        observation = self._observe()
        wear = -sum(
            abs(self.openings[key] - previous[key]) / 100.0
            for key in self.openings
        )
        return observation, RewardVector(actuator_wear=wear), False, False, {
            "backend": "multi-window-physical",
            "actuator_feedback": feedback,
            "physical_opening_readiness": readiness,
            "next_sensor_readings": list(observation["sensor_readings"]),
        }
