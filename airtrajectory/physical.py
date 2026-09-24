from abc import ABC, abstractmethod
from dataclasses import dataclass
import time
from typing import Iterable, List, Optional
from .trajectory import ActuatorFeedback, RewardVector, SemanticAction, Trajectory, TrajectoryStep, TrajectoryStore, TransitionAction

class PhysicalWindowDriver(ABC):
    @abstractmethod
    def read_sensors(self): ...
    @abstractmethod
    def set_position(self, opening_id: str, target_pct: float) -> ActuatorFeedback: ...

@dataclass(frozen=True)
class SafetyDecision:
    proposed: List[TransitionAction]
    executed: List[TransitionAction]
    intervention: Optional[str] = None

class SafetyResolver:
    def resolve(self, observation: dict, actions: Iterable[TransitionAction]) -> SafetyDecision:
        proposed=list(actions)
        if observation.get("rain") and any(a.target_pct>0 for a in proposed):
            return SafetyDecision(proposed,[TransitionAction(a.opening_id,0) for a in proposed],"RAIN_SAFE_CLOSE")
        return SafetyDecision(proposed,list(proposed))

class RulePolicy:
    def __init__(self, opening_id: str, high_co2=1200, low_co2=800):
        self.opening_id,self.high_co2,self.low_co2=opening_id,high_co2,low_co2
    def semantic_action(self, observation):
        co2=observation.get("co2_ppm")
        if co2 is not None and co2>self.high_co2:return SemanticAction("window",self.opening_id,"VENT",50)
        if co2 is not None and co2<self.low_co2:return SemanticAction("window",self.opening_id,"CLOSE",0)
        return SemanticAction("window",self.opening_id,"HOLD",observation.get("opening_pct"))
    def __call__(self, observation):
        a=self.semantic_action(observation); target=observation.get("opening_pct",0) if a.command=="HOLD" else a.value
        return [TransitionAction(self.opening_id,float(target or 0))]

class PhysicalWindowEnvironment:
    def __init__(self, driver: PhysicalWindowDriver, opening_id: str, max_sensor_age_s: float = 10.0, require_measured_feedback: bool = False):
        self.driver,self.opening_id,self.last_feedback=driver,opening_id,None
        self.max_sensor_age_s=max_sensor_age_s
        self.require_measured_feedback=require_measured_feedback
    def _validate_readings(self, readings):
        now=time.time()
        stale=[r.sensor_id for r in readings if now-r.timestamp>self.max_sensor_age_s]
        if stale: raise RuntimeError("stale sensor readings: "+",".join(stale))
    def _validate_feedback(self, feedback):
        if feedback.timestamp<=0: raise RuntimeError("actuator feedback missing timestamp")
        if self.require_measured_feedback and feedback.measured_position_pct is None:
            raise RuntimeError("measured actuator position required but unavailable")
    def _observe(self):
        readings=self.driver.read_sensors(); self._validate_readings(readings); by_type={r.sensor_type:r for r in readings}; f=self.last_feedback
        position=None if f is None else (f.measured_position_pct if f.measured_position_pct is not None else f.estimated_position_pct)
        return {"co2_ppm":by_type.get("co2").value if by_type.get("co2") else None,"rain":bool(by_type.get("rain").value) if by_type.get("rain") else False,"opening_pct":position,"sensor_readings":readings}
    def reset(self):
        return self._observe(),{"backend":"physical-window","driver":type(self.driver).__name__}
    def step(self, actions):
        feedback=[]
        for a in actions:
            if a.opening_id!=self.opening_id:raise KeyError(f"unknown physical opening: {a.opening_id}")
            f=self.driver.set_position(a.opening_id,a.target_pct);self._validate_feedback(f);feedback.append(f);self.last_feedback=f
        return self._observe(),RewardVector(),False,False,{"backend":"physical-window","actuator_feedback":feedback}

def record_physical_trajectory(env,policy,resolver,topology_id,store,steps=1):
    observation,reset_info=env.reset()
    trajectory=Trajectory(topology_id=topology_id,policy_id="rule-policy-v1",environment_kind="physical",context={"reset_info":reset_info})
    for index in range(steps):
        semantic=policy.semantic_action(observation);decision=resolver.resolve(observation,policy(observation))
        nxt,reward,terminated,truncated,info=env.step(decision.executed)
        trajectory.append(TrajectoryStep(index=index,observation={k:v for k,v in observation.items() if k!="sensor_readings"},proposed_actions=decision.proposed,executed_actions=decision.executed,next_observation={k:v for k,v in nxt.items() if k!="sensor_readings"},reward=reward,semantic_actions=[semantic],sensor_readings=list(observation.get("sensor_readings",[])),actuator_feedback=list(info.get("actuator_feedback",[])),intervention=decision.intervention,terminated=terminated or truncated,info={"backend":info.get("backend")}))
        observation=nxt
    store.append(trajectory);return trajectory
