"""Bridge AirTrajectory to WindowPilot with runtime evidence discovery.

The bridge fails closed when /api/capabilities is absent or incomplete.
Only a WindowPilot backend that explicitly reports non-simulated execution and
measured position feedback can become eligible for physical tau0 evidence.
"""
from __future__ import annotations
import json
import time
from typing import Callable
from urllib.request import Request, urlopen

from ..physical import DriverCapabilities, PhysicalWindowDriver
from ..trajectory import ActuatorFeedback, SensorReading


class WindowPilotHTTPDriver(PhysicalWindowDriver):
    def __init__(self, base_url: str="http://127.0.0.1:8000", timeout_s: float=2.0, request_json: Callable|None=None):
        self.base_url=base_url.rstrip("/")
        self.timeout_s=float(timeout_s)
        self._request_json=request_json or self._stdlib_request

    def _capability_payload(self):
        try:
            payload=self._request_json("GET","/api/capabilities",None)
        except Exception:
            return {}
        return payload if isinstance(payload,dict) else {}

    def capabilities(self):
        payload=self._capability_payload()
        execution=payload.get("execution") if isinstance(payload.get("execution"),dict) else {}
        return DriverCapabilities(
            transport=str(execution.get("transport") or "windowpilot-http-unknown"),
            simulated=bool(execution.get("simulated",True)),
            measured_position=bool(execution.get("measured_position",False)),
            sensor_types=("co2","rain","temperature","humidity","wind_speed"),
        )

    def _stdlib_request(self, method: str, path: str, payload=None):
        body=None if payload is None else json.dumps(payload).encode("utf-8")
        req=Request(
            self.base_url+path,
            data=body,
            method=method,
            headers={"Content-Type":"application/json"},
        )
        with urlopen(req, timeout=self.timeout_s) as response:
            return json.loads(response.read().decode("utf-8"))

    def _state(self):
        payload=self._request_json("GET","/api/state",None)
        thing=payload.get("thing_model")
        if not isinstance(thing,dict):
            raise RuntimeError("WindowPilot /api/state missing thing_model")
        return thing

    def read_sensors(self):
        sensors=self._state().get("sensors",{})
        now=time.time()
        rows=[]
        mapping=(
            ("co2_ppm","co2","ppm"),
            ("rain","rain","bool"),
            ("temp_indoor","temperature","C"),
            ("humidity","humidity","pct"),
            ("wind_speed","wind_speed","m/s"),
        )
        for key,sensor_type,unit in mapping:
            if key not in sensors or sensors[key] is None:
                continue
            value=sensors[key]
            if isinstance(value,bool): value=float(value)
            rows.append(SensorReading(
                sensor_id="windowpilot-"+key,
                sensor_type=sensor_type,
                value=float(value),
                unit=unit,
                timestamp=now,
                quality="simulated-windowpilot-receipt-time",
            ))
        return rows

    def set_position(self, opening_id: str, target_pct: float):
        target=float(target_pct)
        if not 0 <= target <= 100:
            raise ValueError("target_pct must be in [0,100]")
        if target <= 0:
            self._request_json("POST","/api/window/close",{})
        else:
            self._request_json("POST","/api/window/open",{"target_pct":target})
        caps_payload=self._capability_payload()
        execution=caps_payload.get("execution") if isinstance(caps_payload.get("execution"),dict) else {}
        feedback=caps_payload.get("position_feedback") if isinstance(caps_payload.get("position_feedback"),dict) else {}
        if execution.get("simulated") is False and execution.get("measured_position") is True:
            if feedback.get("measured") is not True or feedback.get("position_pct") is None:
                raise RuntimeError("WindowPilot advertises measured position but returned no measured feedback")
            ts=float(feedback.get("timestamp") or 0)
            if ts <= 0:
                raise RuntimeError("WindowPilot measured feedback missing timestamp")
            return ActuatorFeedback(
                actuator_id=opening_id,
                timestamp=ts,
                measured_position_pct=float(feedback["position_pct"]),
                quality=str(feedback.get("quality") or "measured-windowpilot"),
            )

        state=self._state()
        position=state.get("window",{}).get("open_pct")
        if position is None:
            raise RuntimeError("WindowPilot state missing window.open_pct")
        return ActuatorFeedback(
            actuator_id=opening_id,
            timestamp=time.time(),
            estimated_position_pct=float(position),
            quality="windowpilot-estimated-state",
        )
