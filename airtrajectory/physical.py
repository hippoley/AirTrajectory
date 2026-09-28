from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
import time
from typing import Iterable, List, Optional
from .trajectory import ActuatorFeedback, RewardVector, SemanticAction, Trajectory, TrajectoryStep, TrajectoryStore, TransitionAction
from .commissioning import validate_commissioning_behavior_context
from .sensor_lineage import validate_sensor_evidence_context
from .lineage import (
    compare_hardware_site_lineage,
    compare_hardware_thingmodel_lineage,
    sensor_binding_matches_site,
    sensor_binding_valid,
)

@dataclass(frozen=True)
class DriverCapabilities:
    transport: str
    simulated: bool
    measured_position: bool
    sensor_types: tuple[str, ...] = ()

class PhysicalWindowDriver(ABC):
    @abstractmethod
    def read_sensors(self): ...
    @abstractmethod
    def set_position(self, opening_id: str, target_pct: float) -> ActuatorFeedback: ...
    @abstractmethod
    def capabilities(self) -> DriverCapabilities: ...
    def read_position_feedback(self, opening_id: str) -> Optional[ActuatorFeedback]:
        """Optional zero-motion measured position snapshot."""
        return None

@dataclass(frozen=True)
class SafetyDecision:
    proposed: List[TransitionAction]
    executed: List[TransitionAction]
    intervention: Optional[str] = None

class SafetyResolver:
    def resolve(self, observation: dict, actions: Iterable[TransitionAction]) -> SafetyDecision:
        proposed=list(actions)
        opening=any(a.target_pct>0 for a in proposed)
        if opening and observation.get("rain") is None:
            return SafetyDecision(proposed,[TransitionAction(a.opening_id,0) for a in proposed],"RAIN_EVIDENCE_MISSING")
        if observation.get("rain") and opening:
            return SafetyDecision(proposed,[TransitionAction(a.opening_id,0) for a in proposed],"RAIN_SAFE_CLOSE")
        return SafetyDecision(proposed,list(proposed))

class RulePolicy:
    policy_id="rule-policy-v1"
    def __init__(self, opening_id: str, high_co2=1200, low_co2=800):
        self.opening_id,self.high_co2,self.low_co2=opening_id,high_co2,low_co2
    def semantic_action(self, observation):
        co2=observation.get("co2_ppm")
        if co2 is not None and co2>self.high_co2:return SemanticAction("window",self.opening_id,"VENT",50)
        if co2 is not None and co2<self.low_co2:return SemanticAction("window",self.opening_id,"CLOSE",0)
        return SemanticAction("window",self.opening_id,"HOLD",observation.get("opening_pct"))
    def __call__(self, observation):
        a=self.semantic_action(observation)
        if a.command=="HOLD" and observation.get("opening_pct") is None:
            return []
        target=observation.get("opening_pct") if a.command=="HOLD" else a.value
        return [TransitionAction(self.opening_id,float(target))]

class Tau0ProbePolicy:
    """Bounded reality-contact probe used only for physical tau0 capture."""

    policy_id="physical-tau0-probe-v1"

    def __init__(
        self,
        opening_id: str,
        target_pct: float=5.0,
        start_tolerance_pct: float=1.0,
        minimum_reality_delta_pct: float=2.0,
    ):
        target=float(target_pct)
        start_tol=float(start_tolerance_pct)
        min_delta=float(minimum_reality_delta_pct)
        if not 0 < target <= 5.0:
            raise ValueError("tau0 target_pct must be >0 and <=5%")
        if not 0 <= start_tol <= 1.0:
            raise ValueError("tau0 start_tolerance_pct must be in [0,1]")
        if not 0 < min_delta <= target:
            raise ValueError("tau0 minimum_reality_delta_pct must be >0 and <= target")
        self.opening_id=opening_id
        self.target_pct=target
        self.start_tolerance_pct=start_tol
        self.minimum_reality_delta_pct=min_delta

    def capture_policy(self):
        return {
            "policy_id":self.policy_id,
            "target_pct":self.target_pct,
            "max_target_pct":5.0,
            "start_tolerance_pct":self.start_tolerance_pct,
            "minimum_reality_delta_pct":self.minimum_reality_delta_pct,
            "requires_measured_pre_action_position":True,
        }

    def _require_start(self, observation):
        position=observation.get("opening_pct")
        if position is None:
            raise RuntimeError("physical tau0 requires measured pre-action position")
        position=float(position)
        if not 0 <= position <= 100:
            raise RuntimeError("physical tau0 pre-action position is outside [0,100]")
        if position > self.start_tolerance_pct:
            raise RuntimeError(
                f"physical tau0 requires near-closed start <= {self.start_tolerance_pct:.2f}%; "
                f"observed {position:.2f}%"
            )
        return position

    def semantic_action(self, observation):
        self._require_start(observation)
        return SemanticAction("window",self.opening_id,"TAU0_PROBE",self.target_pct)

    def __call__(self, observation):
        self._require_start(observation)
        return [TransitionAction(self.opening_id,self.target_pct)]

class PhysicalWindowEnvironment:
    def __init__(
        self,
        driver: PhysicalWindowDriver,
        opening_id: str,
        max_sensor_age_s: float = 10.0,
        require_measured_feedback: bool = False,
        max_feedback_age_s: float = 10.0,
        post_action_sensor_timeout_s: float = 10.0,
        sensor_poll_interval_s: float = 0.1,
        sleep_fn=time.sleep,
        clock_fn=time.time,
    ):
        self.driver,self.opening_id,self.last_feedback=driver,opening_id,None
        self.max_sensor_age_s=max_sensor_age_s
        self.max_feedback_age_s=max_feedback_age_s
        self.require_measured_feedback=require_measured_feedback
        self.post_action_sensor_timeout_s=float(post_action_sensor_timeout_s)
        self.sensor_poll_interval_s=float(sensor_poll_interval_s)
        self._sleep=sleep_fn
        self._clock=clock_fn
    def _validate_readings(self, readings):
        now=time.time()
        stale=[r.sensor_id for r in readings if now-r.timestamp>self.max_sensor_age_s]
        if stale: raise RuntimeError("stale sensor readings: "+",".join(stale))
    def _validate_feedback(self, feedback):
        if feedback.timestamp<=0: raise RuntimeError("actuator feedback missing timestamp")
        age=time.time()-feedback.timestamp
        if age>self.max_feedback_age_s: raise RuntimeError(f"stale actuator feedback: {age:.3f}s")
        if self.require_measured_feedback and feedback.measured_position_pct is None:
            raise RuntimeError("measured actuator position required but unavailable")
    def _observation_from_readings(self, readings):
        self._validate_readings(readings); by_type={r.sensor_type:r for r in readings}; f=self.last_feedback
        position=None if f is None else (f.measured_position_pct if f.measured_position_pct is not None else f.estimated_position_pct)
        return {"co2_ppm":by_type.get("co2").value if by_type.get("co2") else None,"rain":bool(by_type.get("rain").value) if by_type.get("rain") else None,"opening_pct":position,"sensor_readings":readings}
    def _observe(self):
        return self._observation_from_readings(self.driver.read_sensors())
    def _observe_after(self, min_timestamp):
        deadline=self._clock()+self.post_action_sensor_timeout_s
        last_reason="no fresh CO2/rain sample"
        while self._clock() <= deadline:
            readings=self.driver.read_sensors()
            self._validate_readings(readings)
            by_type={r.sensor_type:r for r in readings}
            required=[by_type.get("co2"),by_type.get("rain")]
            if all(r is not None for r in required):
                stale=[r.sensor_type for r in required if r.timestamp <= min_timestamp]
                if not stale:
                    return self._observation_from_readings(readings)
                last_reason="post-action sample not newer than actuator feedback: "+",".join(stale)
            self._sleep(self.sensor_poll_interval_s)
        raise RuntimeError("post-action sensor timeout: "+last_reason)
    def reset(self):
        caps=self.driver.capabilities()
        initial_feedback=self.driver.read_position_feedback(self.opening_id)
        if initial_feedback is not None:
            self._validate_feedback(initial_feedback)
            self.last_feedback=initial_feedback
        return self._observe(),{
            "backend":"physical-window",
            "driver":type(self.driver).__name__,
            "driver_capabilities":asdict(caps),
            "initial_position_feedback":None if initial_feedback is None else asdict(initial_feedback),
            "evidence_kind":"synthetic" if caps.simulated else "physical",
        }
    def step(self, actions):
        feedback=[]
        for a in actions:
            if a.opening_id!=self.opening_id:raise KeyError(f"unknown physical opening: {a.opening_id}")
            f=self.driver.set_position(a.opening_id,a.target_pct);self._validate_feedback(f);feedback.append(f);self.last_feedback=f
        min_feedback_ts=max((f.timestamp for f in feedback),default=0.0)
        nxt=self._observe_after(min_feedback_ts) if feedback else self._observe()
        return nxt,RewardVector(),False,False,{
            "backend":"physical-window",
            "actuator_feedback":feedback,
            "next_sensor_readings":list(nxt.get("sensor_readings",[])),
        }

def record_physical_trajectory(env,policy,resolver,topology_id,store,steps=1,context_extra=None):
    observation,reset_info=env.reset()
    environment_kind="synthetic" if reset_info.get("driver_capabilities",{}).get("simulated",True) else "physical"
    context={"reset_info":reset_info}
    if context_extra:
        context.update(dict(context_extra))
    policy_id=str(getattr(policy,"policy_id","physical-policy-unknown"))
    trajectory=Trajectory(topology_id=topology_id,policy_id=policy_id,environment_kind=environment_kind,context=context)
    for index in range(steps):
        semantic=policy.semantic_action(observation);decision=resolver.resolve(observation,policy(observation))
        nxt,reward,terminated,truncated,info=env.step(decision.executed)
        trajectory.append(TrajectoryStep(index=index,observation={k:v for k,v in observation.items() if k!="sensor_readings"},proposed_actions=decision.proposed,executed_actions=decision.executed,next_observation={k:v for k,v in nxt.items() if k!="sensor_readings"},reward=reward,semantic_actions=[semantic],sensor_readings=list(observation.get("sensor_readings",[])),next_sensor_readings=list(info.get("next_sensor_readings",[])),actuator_feedback=list(info.get("actuator_feedback",[])),intervention=decision.intervention,terminated=terminated or truncated,info={"backend":info.get("backend")}))
        observation=nxt
    store.append(trajectory);return trajectory


@dataclass(frozen=True)
class PhysicalEvidenceReport:
    valid_tau0: bool
    reasons: tuple[str, ...]

def validate_physical_tau0(trajectory: Trajectory) -> PhysicalEvidenceReport:
    reasons=[]
    capture_policy=trajectory.context.get("tau0_capture_policy")
    if not isinstance(capture_policy,dict):
        reasons.append("trajectory missing tau0 capture policy")
        capture_policy={}
    if capture_policy.get("policy_id")!="physical-tau0-probe-v1":
        reasons.append("trajectory tau0 capture policy is not physical-tau0-probe-v1")
    try:
        target_pct=float(capture_policy.get("target_pct"))
        max_target_pct=float(capture_policy.get("max_target_pct"))
        start_tolerance_pct=float(capture_policy.get("start_tolerance_pct"))
        minimum_reality_delta_pct=float(capture_policy.get("minimum_reality_delta_pct"))
        if not 0 < target_pct <= 5.0:
            reasons.append("tau0 capture target must be >0 and <=5%")
        if max_target_pct != 5.0:
            reasons.append("tau0 capture max_target_pct must remain 5%")
        if not 0 <= start_tolerance_pct <= 1.0:
            reasons.append("tau0 capture start tolerance must be in [0,1]%")
        if not 0 < minimum_reality_delta_pct <= target_pct:
            reasons.append("tau0 minimum Reality Delta must be >0 and <= target")
    except (TypeError,ValueError):
        target_pct=max_target_pct=start_tolerance_pct=minimum_reality_delta_pct=None
        reasons.append("trajectory tau0 capture policy has invalid numeric fields")
    caps=trajectory.context.get("reset_info",{}).get("driver_capabilities",{})
    if trajectory.environment_kind!="physical": reasons.append("trajectory is not marked physical")
    if caps.get("simulated",True): reasons.append("driver is simulated or provenance is missing")
    if not caps.get("measured_position",False): reasons.append("driver does not advertise measured position")
    if not trajectory.steps: reasons.append("trajectory has no steps")
    commission_id=trajectory.context.get("commissioning_identity_sha256")
    runtime_identity=trajectory.context.get("runtime_hardware_identity") or {}
    runtime_id=runtime_identity.get("identity_sha256") if isinstance(runtime_identity,dict) else None
    if not commission_id: reasons.append("trajectory missing commissioning hardware identity")
    if not runtime_id: reasons.append("trajectory missing runtime hardware identity")
    elif commission_id and runtime_id!=commission_id:
        reasons.append("commissioning/runtime hardware identity mismatch")

    try:
        lineage=compare_hardware_thingmodel_lineage(
            trajectory.context.get("commissioning_hardware_identity") or {},
            runtime_identity,
            label="runtime",
        )
        if trajectory.context.get("thingmodel_lineage")!=lineage:
            reasons.append("trajectory ThingModel lineage does not match commissioning/runtime identity")
    except RuntimeError as exc:
        reasons.append(str(exc))

    try:
        site_lineage=compare_hardware_site_lineage(
            trajectory.context.get("commissioning_hardware_identity") or {},
            runtime_identity,
            label="runtime",
        )
        if trajectory.context.get("site_lineage")!=site_lineage:
            reasons.append("trajectory physical-site lineage does not match commissioning/runtime identity")
    except RuntimeError as exc:
        reasons.append(str(exc))

    try:
        validate_commissioning_behavior_context(
            trajectory.context.get("commissioning_behavior_witness"),
            trajectory.context.get("commissioning_behavior_sha256"),
        )
    except RuntimeError as exc:
        reasons.append(str(exc))

    sensor_context_keys=(
        "sensor_evidence_origin",
        "runtime_sensor_lineage",
        "sensor_staging_lineage",
        "sensor_evidence_sha256",
    )
    if any(trajectory.context.get(key) is not None for key in sensor_context_keys):
        try:
            validate_sensor_evidence_context(
                sensor_evidence_origin=trajectory.context.get("sensor_evidence_origin"),
                runtime_sensor_lineage=trajectory.context.get("runtime_sensor_lineage"),
                sensor_staging_lineage=trajectory.context.get("sensor_staging_lineage"),
                sensor_evidence_sha256=trajectory.context.get("sensor_evidence_sha256"),
                site_lineage=trajectory.context.get("site_lineage") or {},
                commissioning_identity_sha256=commission_id,
                commissioning_bundle_sha256=trajectory.context.get("commissioning_bundle_sha256"),
            )
        except RuntimeError as exc:
            reasons.append(str(exc))

    preflight_receipt=trajectory.context.get("preflight_receipt_sha256")
    preflight_id=trajectory.context.get("preflight_hardware_identity_sha256")
    gateway_contract=trajectory.context.get("gateway_contract_sha256")
    if not preflight_receipt:
        reasons.append("trajectory missing read-only preflight receipt lineage")
    if not preflight_id:
        reasons.append("trajectory missing preflight hardware identity")
    elif commission_id and preflight_id!=commission_id:
        reasons.append("preflight/commissioning hardware identity mismatch")
    if not gateway_contract:
        reasons.append("trajectory missing gateway contract lineage")
    initial_feedback=trajectory.context.get("reset_info",{}).get("initial_position_feedback")
    initial_position=None
    if not isinstance(initial_feedback,dict):
        reasons.append("trajectory missing measured pre-action position feedback")
    elif initial_feedback.get("measured_position_pct") is None:
        reasons.append("trajectory pre-action position is not measured")
    else:
        try:
            initial_position=float(initial_feedback.get("measured_position_pct"))
            if start_tolerance_pct is not None and initial_position > start_tolerance_pct:
                reasons.append("trajectory pre-action position is not near closed")
        except (TypeError,ValueError):
            reasons.append("trajectory pre-action measured position is invalid")

    reality_delta_observed=False
    max_measured_delta=0.0
    expected_site_lineage=trajectory.context.get("site_lineage") or {}
    for step in trajectory.steps:
        sensor_types={r.sensor_type for r in step.sensor_readings}
        if "co2" not in sensor_types: reasons.append(f"step {step.index} missing CO2 evidence")
        if "rain" not in sensor_types: reasons.append(f"step {step.index} missing rain evidence")
        for reading in step.sensor_readings:
            if reading.sensor_type in ("co2","rain") and not sensor_binding_valid(reading.provenance):
                reasons.append(
                    f"step {step.index} {reading.sensor_type} evidence missing valid ThingModel/site provenance"
                )
            elif reading.sensor_type in ("co2","rain") and not sensor_binding_matches_site(
                reading.provenance,expected_site_lineage
            ):
                reasons.append(
                    f"step {step.index} {reading.sensor_type} evidence belongs to a different physical site contract"
                )

        if any(
            a.target_pct > 5.0 or a.target_pct < 0
            for a in step.proposed_actions+step.executed_actions
        ):
            reasons.append(f"step {step.index} exceeds bounded tau0 target")

        if not step.actuator_feedback:
            reasons.append(f"step {step.index} missing actuator feedback")
        elif any(f.measured_position_pct is None for f in step.actuator_feedback):
            reasons.append(f"step {step.index} lacks measured actuator position")
        elif initial_position is not None:
            for feedback in step.actuator_feedback:
                delta=abs(float(feedback.measured_position_pct)-initial_position)
                max_measured_delta=max(max_measured_delta,delta)
                if (
                    minimum_reality_delta_pct is not None
                    and delta >= minimum_reality_delta_pct
                ):
                    reality_delta_observed=True

        next_types={r.sensor_type for r in step.next_sensor_readings}
        if "co2" not in next_types: reasons.append(f"step {step.index} missing post-action CO2 evidence")
        if "rain" not in next_types: reasons.append(f"step {step.index} missing post-action rain evidence")
        for reading in step.next_sensor_readings:
            if reading.sensor_type in ("co2","rain") and not sensor_binding_valid(reading.provenance):
                reasons.append(
                    f"step {step.index} post-action {reading.sensor_type} evidence missing valid ThingModel/site provenance"
                )
            elif reading.sensor_type in ("co2","rain") and not sensor_binding_matches_site(
                reading.provenance,expected_site_lineage
            ):
                reasons.append(
                    f"step {step.index} post-action {reading.sensor_type} evidence belongs to a different physical site contract"
                )

        if step.actuator_feedback and step.next_sensor_readings:
            feedback_ts=max(f.timestamp for f in step.actuator_feedback)
            if any(r.sensor_type in ("co2","rain") and r.timestamp <= feedback_ts for r in step.next_sensor_readings):
                reasons.append(f"step {step.index} post-action sensor evidence is not newer than actuator feedback")
    if not reality_delta_observed:
        detail=f" (max {max_measured_delta:.3f}%)" if initial_position is not None else ""
        reasons.append("physical tau0 did not produce required measured Reality Delta"+detail)
    return PhysicalEvidenceReport(not reasons,tuple(reasons))
