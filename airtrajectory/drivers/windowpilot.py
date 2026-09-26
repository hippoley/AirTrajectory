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
    def __init__(
        self,
        base_url: str="http://127.0.0.1:8000",
        timeout_s: float=2.0,
        request_json: Callable|None=None,
        feedback_timeout_s: float=5.0,
        feedback_poll_interval_s: float=0.1,
        position_tolerance_pct: float=1.0,
        sleep_fn=time.sleep,
        clock_fn=time.time,
    ):
        self.base_url=base_url.rstrip("/")
        self.timeout_s=float(timeout_s)
        self.feedback_timeout_s=float(feedback_timeout_s)
        self.feedback_poll_interval_s=float(feedback_poll_interval_s)
        self.position_tolerance_pct=float(position_tolerance_pct)
        self._request_json=request_json or self._stdlib_request
        self._sleep=sleep_fn
        self._clock=clock_fn

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
        state=self._state()
        sensors=state.get("sensors",{})
        timestamps=state.get("sensor_timestamps",{}) if isinstance(state.get("sensor_timestamps"),dict) else {}
        evidence=state.get("sensor_evidence",{}) if isinstance(state.get("sensor_evidence"),dict) else {}
        caps=self.capabilities()
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
            if caps.simulated:
                ts=now
                quality="simulated-windowpilot-receipt-time"
                sensor_id="windowpilot-"+key
            else:
                ts_key="temperature" if key=="temp_indoor" else key
                evidence_key="co2_ppm" if key=="co2_ppm" else ("rain" if key=="rain" else ts_key)
                ts=float(timestamps.get(ts_key) or 0)
                ev=evidence.get(evidence_key) if isinstance(evidence.get(evidence_key),dict) else {}
                ev_ts=float(ev.get("timestamp") or 0)
                if ts <= 0:
                    raise RuntimeError(f"WindowPilot hardware sensor {key} missing source timestamp")
                if ev.get("measured") is not True:
                    raise RuntimeError(f"WindowPilot hardware sensor {key} is not backed by measured evidence")
                if ev_ts != ts:
                    raise RuntimeError(f"WindowPilot hardware sensor {key} evidence timestamp mismatch")
                source=str(ev.get("source") or "")
                if not source:
                    raise RuntimeError(f"WindowPilot hardware sensor {key} missing evidence source")
                sensor_id=source
                quality=str(ev.get("quality") or "measured-windowpilot-source-time")
            rows.append(SensorReading(
                sensor_id=sensor_id,
                sensor_type=sensor_type,
                value=float(value),
                unit=unit,
                timestamp=ts,
                quality=quality,
            ))
        return rows

    def set_position(self, opening_id: str, target_pct: float):
        target=float(target_pct)
        if not 0 <= target <= 100:
            raise ValueError("target_pct must be in [0,100]")
        command_started=self._clock()
        if target <= 0:
            self._request_json("POST","/api/window/close",{})
        else:
            self._request_json("POST","/api/window/open",{"target_pct":target})
        caps_payload=self._capability_payload()
        execution=caps_payload.get("execution") if isinstance(caps_payload.get("execution"),dict) else {}
        if execution.get("simulated") is False and execution.get("measured_position") is True:
            deadline=command_started+self.feedback_timeout_s
            last_reason="no measured feedback"
            while self._clock() <= deadline:
                caps_payload=self._capability_payload()
                feedback=caps_payload.get("position_feedback") if isinstance(caps_payload.get("position_feedback"),dict) else {}
                if feedback.get("measured") is True and feedback.get("position_pct") is not None:
                    ts=float(feedback.get("timestamp") or 0)
                    pct=float(feedback["position_pct"])
                    if ts < command_started:
                        last_reason="feedback predates command"
                    elif abs(pct-target) > self.position_tolerance_pct:
                        last_reason=f"measured position {pct:.2f}% has not reached target {target:.2f}%"
                    else:
                        return ActuatorFeedback(
                            actuator_id=opening_id,
                            timestamp=ts,
                            measured_position_pct=pct,
                            quality=str(feedback.get("quality") or "measured-windowpilot"),
                        )
                self._sleep(self.feedback_poll_interval_s)
            raise RuntimeError("WindowPilot measured feedback timeout: "+last_reason)

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
