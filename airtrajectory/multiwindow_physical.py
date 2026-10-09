"""Multi-opening physical execution bus for the ventilation demo.

Each real opening is mapped to its own PhysicalWindowDriver (typically a
WindowPilotHTTPDriver). Internal doors or non-actuated openings may remain as
fixed topology state, but cannot be mistaken for measured hardware.

The bus fails closed when any commanded real opening is not physically
write-ready.
"""
from __future__ import annotations

from dataclasses import asdict
from math import isfinite
import time
from typing import Mapping

from .physical import PhysicalWindowDriver
from .trajectory import ActuatorFeedback, RewardVector, TransitionAction


class PhysicalDispatchUnresolved(RuntimeError):
    """A physical write may have occurred; never blindly retry the batch."""

    def __init__(self, *, attempted: list[str], confirmed: list[str], reason: str):
        self.attempted_openings = tuple(attempted)
        self.confirmed_feedback_openings = tuple(confirmed)
        self.physical_effect_unresolved = True
        super().__init__(
            "physical dispatch outcome unresolved; manual measured reconciliation required: "
            + reason + " (attempted=" + ",".join(attempted)
            + "; feedback=" + ",".join(confirmed) + ")"
        )


class MultiWindowPhysicalEnvironment:
    def __init__(
        self,
        topology,
        drivers: Mapping[str, PhysicalWindowDriver],
        *,
        fixed_openings: Mapping[str, float] | None = None,
        initial_openings: Mapping[str, float] | None = None,
        require_write_ready: bool = True,
        max_sensor_age_s: float = 10.0,
        clock_fn=time.time,
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
        for opening_id, position in self.openings.items():
            if not isfinite(position) or not 0 <= position <= 100:
                raise ValueError(f"invalid initial opening percentage: {opening_id}")
        self.require_write_ready = bool(require_write_ready)
        self.max_sensor_age_s = float(max_sensor_age_s)
        if not isfinite(self.max_sensor_age_s) or self.max_sensor_age_s <= 0:
            raise ValueError("max_sensor_age_s must be finite and positive")
        self._clock = clock_fn
        self.last_feedback: dict[str, ActuatorFeedback] = {}
        # Session-local quarantine only; not durable field evidence.
        self.dispatch_unresolved = False

        topology.validate()
        unknown_fixed = set(self.fixed_openings) - set(topology.openings)
        if unknown_fixed:
            raise ValueError("fixed openings reference unknown topology IDs: " + ",".join(sorted(unknown_fixed)))
        unknown_initial = set(initial_openings or {}) - set(topology.openings)
        if unknown_initial:
            raise ValueError("initial openings reference unknown topology IDs: " + ",".join(sorted(unknown_initial)))
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
        now = self._clock()
        rain = None
        sensor_rows = []
        for opening_id, driver in self.drivers.items():
            zone = self._zone_for_opening(opening_id)
            for reading in driver.read_sensors():
                if not isinstance(reading.timestamp,(int,float)) or not isfinite(reading.timestamp) or reading.timestamp<=0:
                    raise RuntimeError(f"{opening_id} invalid sensor timestamp")
                if reading.timestamp > now + 1.0:
                    raise RuntimeError(f"{opening_id} future sensor timestamp")
                if now - reading.timestamp > self.max_sensor_age_s:
                    raise RuntimeError(f"{opening_id} stale sensor timestamp")
                if not isinstance(reading.value,(int,float)) or not isfinite(reading.value):
                    raise RuntimeError(f"{opening_id} invalid sensor value")
                sensor_rows.append(reading)
                if reading.sensor_type == "co2" and zone is not None:
                    if reading.value < 0:
                        raise RuntimeError(f"{opening_id} invalid CO2 concentration")
                    co2_candidates.setdefault(zone, []).append(reading)
                elif reading.sensor_type == "rain":
                    if reading.value not in (0,1):
                        raise RuntimeError(f"{opening_id} invalid rain evidence")
                    rain = bool(reading.value) if rain is None else rain or bool(reading.value)

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
        if self.dispatch_unresolved:
            raise RuntimeError(
                "physical dispatch outcome unresolved; no new writes before "
                "independent measured reconciliation"
            )
        actions = list(actions)
        # Validate all action identities and ranges before dispatching any
        # command. No atomicity is claimed across independent drivers.
        seen = set()
        for action in actions:
            if action.opening_id in seen:
                raise ValueError(f"duplicate physical action: {action.opening_id}")
            seen.add(action.opening_id)
            if not isinstance(action.target_pct,(int,float)) or not isfinite(action.target_pct) or not 0<=action.target_pct<=100:
                raise ValueError(f"invalid target_pct: {action.opening_id}")
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

        # A missing or wet rain signal cannot authorize an *increase* in
        # exterior-window opening. Doors are not exterior windows.
        # The sensor read is pre-dispatch and must never be synthesized.
        if any(
            self.topology.openings[action.opening_id].kind=="window"
            and (
                self.topology.openings[action.opening_id].source==self.topology.outside_id
                or self.topology.openings[action.opening_id].target==self.topology.outside_id
            )
            and action.target_pct>self.openings[action.opening_id]
            for action in physical_actions
        ):
            pre=self._observe()
            if pre["rain"] is not False:
                raise RuntimeError("rain or missing rain evidence blocks exterior opening increase")

        readiness = {}
        if physical_actions and self.require_write_ready:
            readiness = self._assert_write_ready(
                [action.opening_id for action in physical_actions]
            )

        feedback = []
        previous = dict(self.openings)
        attempted: list[str] = []
        confirmed: list[str] = []
        for action in physical_actions:
            driver = self.drivers[action.opening_id]
            attempted.append(action.opening_id)
            try:
                item = driver.set_position(action.opening_id, action.target_pct)
                if item.actuator_id != action.opening_id:
                    raise RuntimeError("actuator feedback identity mismatch")
                measured = item.measured_position_pct
                if measured is None:
                    raise RuntimeError("measured position unavailable after write")
                if not isfinite(measured) or not 0 <= measured <= 100:
                    raise RuntimeError("invalid measured actuator position")
                feedback.append(item)
                self.last_feedback[action.opening_id] = item
                self.openings[action.opening_id] = float(measured)
                confirmed.append(action.opening_id)
            except Exception as exc:
                # A transport error does NOT mean the write was not applied.
                # Quarantine this instance rather than retrying or returning
                # a falsely complete next origin.
                self.dispatch_unresolved = True
                raise PhysicalDispatchUnresolved(
                    attempted=attempted, confirmed=confirmed,
                    reason=str(exc),
                ) from exc

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
