"""Bridge AirTrajectory to WindowPilot with runtime evidence discovery.

The bridge fails closed when /api/capabilities is absent or incomplete.
Only a WindowPilot backend that explicitly reports non-simulated execution and
measured position feedback can become eligible for physical tau0 evidence.
"""
from __future__ import annotations
import hashlib
import json
import time
import uuid
from typing import Callable
from urllib.request import Request, urlopen

from ..lineage import sensor_binding_valid
from ..physical import DriverCapabilities, PhysicalWindowDriver
from ..trajectory import ActuatorFeedback, SensorReading


class WindowPilotHTTPDriver(PhysicalWindowDriver):
    def __init__(
        self,
        base_url: str="http://127.0.0.1:8000",
        timeout_s: float=2.0,
        request_json: Callable|None=None,
        response_adapter: Callable|None=None,
        headers: dict[str,str]|None=None,
        feedback_timeout_s: float=5.0,
        feedback_poll_interval_s: float=0.1,
        position_tolerance_pct: float=1.0,
        stop_on_feedback_timeout: bool=True,
        sleep_fn=time.sleep,
        clock_fn=time.time,
    ):
        self.base_url=base_url.rstrip("/")
        self.timeout_s=float(timeout_s)
        self.feedback_timeout_s=float(feedback_timeout_s)
        self.feedback_poll_interval_s=float(feedback_poll_interval_s)
        self.position_tolerance_pct=float(position_tolerance_pct)
        self.stop_on_feedback_timeout=bool(stop_on_feedback_timeout)
        self._raw_request_json=request_json or self._stdlib_request
        self._response_adapter=response_adapter
        self._headers=dict(headers or {})
        self._sleep=sleep_fn
        self._clock=clock_fn
        self.last_command_ack=None
        self.last_safety_stop_ack=None
        self.last_command_request_id=None

    def _request_json(self, method: str, path: str, payload=None):
        raw=self._raw_request_json(method,path,payload)
        if (
            method == "GET"
            and self._response_adapter is not None
            and path in {
                "/api/capabilities",
                "/api/physical-readiness",
                "/api/state",
            }
        ):
            return self._response_adapter(path, raw)
        return raw


    @staticmethod
    def _ack_sha256(payload):
        raw=json.dumps(
            payload,
            sort_keys=True,
            separators=(",",":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _validate_command_ack(
        self,
        response,
        *,
        expected_action: str,
        expected_target,
        require_physical: bool,
        expected_request_id: str | None = None,
    ):
        if not isinstance(response,dict):
            raise RuntimeError("WindowPilot command response is not an object")
        ack=response.get("command_ack")
        if not isinstance(ack,dict):
            raise RuntimeError("WindowPilot command response missing command_ack")
        contract=str(ack.get("receipt") or "")
        if contract not in {
            "windowpilot-command-ack-v1",
            "windowpilot-command-ack-v2",
        }:
            raise RuntimeError("WindowPilot command_ack contract is unsupported")
        if contract=="windowpilot-command-ack-v2":
            try:
                request_id=str(uuid.UUID(str(ack.get("request_id") or "")))
                command_id=str(uuid.UUID(str(ack.get("command_id") or "")))
            except (ValueError,TypeError,AttributeError) as exc:
                raise RuntimeError(
                    "WindowPilot command_ack v2 request/command identity is invalid"
                ) from exc
            if expected_request_id is not None and request_id!=expected_request_id:
                raise RuntimeError(
                    "WindowPilot command_ack request_id does not match this command request"
                )
        elif expected_request_id is not None:
            raise RuntimeError(
                "WindowPilot command_ack v1 cannot satisfy request-bound execution"
            )
        if ack.get("accepted") is not True:
            raise RuntimeError("WindowPilot command was not acknowledged as accepted")
        if str(ack.get("action") or "")!=str(expected_action):
            raise RuntimeError("WindowPilot command_ack action mismatch")
        actual_target=ack.get("target_pct")
        if expected_target is None:
            if actual_target is not None:
                raise RuntimeError("WindowPilot STOP command_ack unexpectedly has target_pct")
        elif actual_target is None or abs(float(actual_target)-float(expected_target))>1e-9:
            raise RuntimeError("WindowPilot command_ack target mismatch")
        if float(ack.get("accepted_at") or 0)<=0:
            raise RuntimeError("WindowPilot command_ack accepted_at is invalid")
        identity=str(ack.get("hardware_identity_sha256") or "")
        if len(identity)!=64 or any(ch not in "0123456789abcdef" for ch in identity.lower()):
            raise RuntimeError("WindowPilot command_ack hardware identity is invalid")
        provided=str(ack.get("command_ack_sha256") or "")
        payload={key:value for key,value in ack.items() if key!="command_ack_sha256"}
        if provided!=self._ack_sha256(payload):
            raise RuntimeError("WindowPilot command_ack SHA-256 mismatch")
        if require_physical:
            if ack.get("simulated") is not False:
                raise RuntimeError("WindowPilot physical command_ack is marked simulated")
            if ack.get("physical_write_ready") is not True:
                raise RuntimeError("WindowPilot physical command_ack lacks write authorization")
            if ack.get("write_contract_ready") is not True:
                raise RuntimeError("WindowPilot physical command_ack lacks write contract")
            if ack.get("motion_semantics_ready") is not True:
                raise RuntimeError("WindowPilot physical command_ack lacks motion semantics")
            if ack.get("evidence_kind")!="physical-command-accepted":
                raise RuntimeError("WindowPilot physical command_ack evidence kind is invalid")
        return dict(ack)

    def contract_mapping_identity(self):
        adapter=self._response_adapter
        if adapter is None:
            return {
                "profile_id": None,
                "profile_sha256": None,
            }
        return {
            "profile_id": getattr(adapter,"profile_id",None),
            "profile_sha256": getattr(adapter,"profile_sha256",None),
        }

    def _capability_payload(self):
        try:
            payload=self._request_json("GET","/api/capabilities",None)
        except Exception:
            return {}
        return payload if isinstance(payload,dict) else {}

    def physical_readiness(self):
        payload=self._request_json("GET","/api/physical-readiness",None)
        if not isinstance(payload,dict):
            raise RuntimeError("WindowPilot /api/physical-readiness returned invalid payload")
        return payload

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
            headers={
                "Content-Type":"application/json",
                **self._headers,
            },
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
            provenance={}
            if caps.simulated:
                ts=now
                quality="simulated-windowpilot-receipt-time"
                sensor_id="windowpilot-"+key
            else:
                ts_key="temperature" if key=="temp_indoor" else key
                evidence_key="co2_ppm" if key=="co2_ppm" else ("rain" if key=="rain" else ts_key)
                required=key in ("co2_ppm","rain")
                ts=float(timestamps.get(ts_key) or 0)
                ev=evidence.get(evidence_key) if isinstance(evidence.get(evidence_key),dict) else {}
                ev_ts=float(ev.get("timestamp") or 0)
                source=str(ev.get("source") or "")
                valid=(
                    ts > 0
                    and ev.get("measured") is True
                    and ev_ts == ts
                    and bool(source)
                )
                if not valid:
                    if required:
                        if ts <= 0:
                            raise RuntimeError(f"WindowPilot hardware sensor {key} missing source timestamp")
                        if ev.get("measured") is not True:
                            raise RuntimeError(f"WindowPilot hardware sensor {key} is not backed by measured evidence")
                        if ev_ts != ts:
                            raise RuntimeError(f"WindowPilot hardware sensor {key} evidence timestamp mismatch")
                        raise RuntimeError(f"WindowPilot hardware sensor {key} missing evidence source")
                    continue
                sensor_id=source
                quality=str(ev.get("quality") or "measured-windowpilot-source-time")
                binding=ev.get("thingmodel_binding")
                if required and not sensor_binding_valid(binding):
                    raise RuntimeError(
                        f"WindowPilot hardware sensor {key} missing valid ThingModel/site binding"
                    )
                provenance=dict(binding or {})
            rows.append(SensorReading(
                sensor_id=sensor_id,
                sensor_type=sensor_type,
                value=float(value),
                unit=unit,
                timestamp=ts,
                quality=quality,
                provenance=provenance,
            ))
        return rows

    def set_position(self, opening_id: str, target_pct: float):
        target=float(target_pct)
        if not 0 <= target <= 100:
            raise ValueError("target_pct must be in [0,100]")
        pre_caps=self._capability_payload()
        pre_execution=(
            pre_caps.get("execution")
            if isinstance(pre_caps.get("execution"),dict)
            else {}
        )
        physical=pre_execution.get("simulated") is False
        ack_contract=str(pre_caps.get("command_ack_contract") or "")
        idempotency_contract=str(
            pre_caps.get("command_idempotency_contract") or ""
        )
        if physical and ack_contract!="windowpilot-command-ack-v2":
            raise RuntimeError(
                "WindowPilot physical writes require windowpilot-command-ack-v2"
            )
        if (
            physical
            and idempotency_contract!="durable-request-ledger-v1"
        ):
            raise RuntimeError(
                "WindowPilot physical writes require "
                "durable-request-ledger-v1"
            )

        command_started=self._clock()
        request_id=(
            str(uuid.uuid4())
            if ack_contract=="windowpilot-command-ack-v2"
            else None
        )
        self.last_command_request_id=request_id
        if target <= 0:
            request_payload={} if request_id is None else {"request_id":request_id}
            response=self._request_json("POST","/api/window/close",request_payload)
            action="close"
            expected_target=0.0
        else:
            request_payload={"target_pct":target}
            if request_id is not None:
                request_payload["request_id"]=request_id
            response=self._request_json("POST","/api/window/open",request_payload)
            action="open"
            expected_target=target

        self.last_command_ack=None
        if physical:
            self.last_command_ack=self._validate_command_ack(
                response,
                expected_action=action,
                expected_target=expected_target,
                require_physical=True,
                expected_request_id=request_id,
            )
        elif isinstance(response,dict) and isinstance(response.get("command_ack"),dict):
            self.last_command_ack=self._validate_command_ack(
                response,
                expected_action=action,
                expected_target=expected_target,
                require_physical=False,
                expected_request_id=request_id,
            )

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
                    ack_accepted_at=float(
                        (self.last_command_ack or {}).get("accepted_at") or 0
                    )
                    if ts < command_started:
                        last_reason="feedback predates command"
                    elif ack_accepted_at > 0 and ts < ack_accepted_at:
                        last_reason="feedback predates command acknowledgement"
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
            stop_note=""
            if self.stop_on_feedback_timeout:
                try:
                    stop_request_id=(
                        str(uuid.uuid4())
                        if ack_contract=="windowpilot-command-ack-v2"
                        else None
                    )
                    stop_payload=(
                        {}
                        if stop_request_id is None
                        else {"request_id":stop_request_id}
                    )
                    ack=self._request_json("POST","/api/window/stop",stop_payload)
                    if isinstance(ack,dict) and ack.get("ok") is True:
                        self.last_safety_stop_ack=None
                        if physical:
                            self.last_safety_stop_ack=self._validate_command_ack(
                                ack,
                                expected_action="stop",
                                expected_target=None,
                                require_physical=True,
                                expected_request_id=stop_request_id,
                            )
                        stop_note="; safety STOP acknowledged"
                    else:
                        stop_note="; safety STOP was not acknowledged"
                except Exception as exc:
                    stop_note=f"; safety STOP failed: {exc}"
            raise RuntimeError(
                "WindowPilot measured feedback timeout: "+last_reason+stop_note
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
