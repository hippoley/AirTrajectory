"""CONTAM/contamxpy adapter.

This module wraps the real NIST Python binding when installed. Tests may inject a
binding factory, but that does not count as a real CONTAM execution.
"""
from dataclasses import dataclass
from pathlib import Path
import importlib
from typing import Callable, Dict, Optional

from .environment import VentilationEnvironment
from .trajectory import RewardVector, TransitionAction, ScalarControlAction

def co2_mass_fraction_to_ppm(value: float) -> float:
    # ppmv ~= mass fraction * M_air / M_CO2 * 1e6
    return float(value) * (28.96546 / 44.0095) * 1_000_000.0

@dataclass(frozen=True)
class ContamControl:
    control_number: int = 0
    control_name: str | None = None
    closed_value: float = 0.0
    open_value: float = 1.0

    def value_for_pct(self,pct:float)->float:
        return self.closed_value+(self.open_value-self.closed_value)*(float(pct)/100.0)

@dataclass(frozen=True)
class ContamScalarControl:
    control_number: int = 0
    control_name: str | None = None
    command_min: float = 0.0
    command_max: float = 1.0
    control_min: float = 0.0
    control_max: float = 1.0

    def value_for_command(self,command:float)->float:
        x=float(command)
        if self.command_max<=self.command_min:
            raise ValueError("command_max must be greater than command_min")
        if x<self.command_min or x>self.command_max:
            raise ValueError(
                f"scalar command {x} outside [{self.command_min}, {self.command_max}]"
            )
        ratio=(x-self.command_min)/(self.command_max-self.command_min)
        return self.control_min+(self.control_max-self.control_min)*ratio


class ContamXSession:
    """Thin lifecycle wrapper around NIST contamxpy.cxLib."""
    def __init__(self,prj_path:str|Path,binding_factory:Optional[Callable]=None,verbosity:int=0,ambient:Optional[dict]=None,initial_input_controls:Optional[dict]=None):
        self.prj_path=Path(prj_path)
        self.binding_factory=binding_factory
        self.verbosity=verbosity
        self.ambient=dict(ambient or {})
        self.initial_input_controls={int(k):dict(v) for k,v in (initial_input_controls or {}).items()}
        self.engine=None
        self.started=False

    def _factory(self):
        if self.binding_factory is not None: return self.binding_factory
        try:
            module=importlib.import_module("contamxpy")
        except ImportError as exc:
            raise RuntimeError("contamxpy is not installed; install AirTrajectory[contam]") from exc
        factory=getattr(module,"cxLib",None)
        if factory is None:
            raise RuntimeError("installed contamxpy does not expose cxLib")
        return factory

    def setup(self):
        if not self.prj_path.exists():
            raise FileNotFoundError(self.prj_path)
        factory=self._factory()
        # contamxpy 0.0.9 binds one cxLib instance to a specific PRJ path.
        init_callback=None
        if self.ambient:
            ambient=dict(self.ambient)
            def init_callback(cx):
                if "pressure_pa" in ambient: cx.setAmbtPressure(float(ambient["pressure_pa"]))
                if "wind_speed_m_s" in ambient: cx.setAmbtWindSpeed(float(ambient["wind_speed_m_s"]))
                if "wind_direction_deg" in ambient: cx.setAmbtWindDirection(float(ambient["wind_direction_deg"]))
                if "temperature_k" in ambient: cx.setAmbtTemperature(float(ambient["temperature_k"]))
                for number,value in (ambient.get("mass_fractions") or {}).items():
                    cx.setAmbtMassFraction(int(number),float(value))
        self.engine=factory(str(self.prj_path),0,True,init_callback)
        if hasattr(self.engine,"setVerbosity"): self.engine.setVerbosity(self.verbosity)
        setup_status=self.engine.setupSimulation(1)
        if setup_status not in (None,0):
            raise RuntimeError(f"ContamX setupSimulation failed with status {setup_status}")
        self.started=True
        controls=list(getattr(self.engine,"inputControls",[]))
        for index,spec in self.initial_input_controls.items():
            if index<1 or index>len(controls):
                raise RuntimeError(f"CONTAM initial input-control index out of range: {index}")
            expected=str(spec.get("name") or "")
            actual=str(getattr(controls[index-1],"name",""))
            if expected and actual!=expected:
                raise RuntimeError(f"CONTAM input-control mapping drift at {index}: expected {expected}, got {actual}")
            self.engine.setInputControlValue(int(index),float(spec["value"]))
        return {
            "version":self.engine.getVersion() if hasattr(self.engine,"getVersion") else "unknown",
            "zones":getattr(self.engine,"nZones",None),
            "paths":getattr(self.engine,"nPaths",None),
            "input_controls":getattr(self.engine,"nInputControls",None),
            "input_control_names":[str(getattr(ctrl,"name","")) for ctrl in getattr(self.engine,"inputControls",[])],
            "output_controls":getattr(self.engine,"nOutputControls",None),
            "output_control_names":[str(getattr(ctrl,"name","")) for ctrl in getattr(self.engine,"outputControls",[])],
            "time_step_s":self.engine.getSimTimeStep() if hasattr(self.engine,"getSimTimeStep") else None,
        }

    def _require(self,*names):
        if not self.started or self.engine is None: raise RuntimeError("CONTAM session not started")
        for name in names:
            fn=getattr(self.engine,name,None)
            if fn is not None: return fn
        raise RuntimeError("contamxpy binding missing required method: "+"/".join(names))

    def input_control_index(self,name:str)->int:
        if not self.started or self.engine is None:
            raise RuntimeError("CONTAM session not started")
        expected=str(name)
        for index,ctrl in enumerate(getattr(self.engine,"inputControls",[]),start=1):
            if str(getattr(ctrl,"name",""))==expected:
                return index
        raise KeyError(f"CONTAM input control not found: {expected}")

    def set_input_control(self,control_number:int,value:float):
        self._require("setInputControlValue")(int(control_number),float(value))

    def set_named_input_control(self,name:str,value:float):
        self.set_input_control(self.input_control_index(name),value)

    def zone_mass_fraction(self,zone_number:int,contaminant_number:int)->float:
        return float(self._require("getZoneMassFraction","getZoneMF")(int(zone_number),int(contaminant_number)))

    def path_flow(self,path_number:int)->float:
        value=self._require("getPathFlow")(int(path_number))
        if isinstance(value,(list,tuple)):
            if not value:
                raise RuntimeError("contamxpy getPathFlow returned an empty flow vector")
            return float(sum(float(x) for x in value))
        return float(value)

    def step(self):
        self._require("doSimStep","doCosimStep")(1)

    def close(self):
        if self.started and self.engine is not None:
            self._require("endSimulation")()
        self.started=False

    def __enter__(self):
        self.setup(); return self

    def __exit__(self,*_):
        self.close()

class CONTAMEnvironment(VentilationEnvironment):
    """AirTrajectory environment backed by an actual CONTAM PRJ co-simulation."""
    def __init__(
        self,topology,prj_path,zone_numbers:Dict[str,int],opening_controls:Dict[str,ContamControl],
        co2_contaminant_index:int=0,path_numbers:Optional[Dict[str,int]]=None,max_steps:int=120,
        binding_factory:Optional[Callable]=None,fixed_openings:Optional[Dict[str,float]]=None,
        initial_openings:Optional[Dict[str,float]]=None,rain:Optional[bool]=False,
        initial_co2_ppm:Optional[Dict[str,float]]=None,ambient:Optional[dict]=None,
        initial_input_controls:Optional[dict]=None,warm_start:bool=True,
    ):
        self.topology=topology; self.prj_path=Path(prj_path); self.zone_numbers=dict(zone_numbers)
        self.opening_controls=dict(opening_controls); self.co2_contaminant_index=co2_contaminant_index
        self.path_numbers=dict(path_numbers or {}); self.max_steps=max_steps; self.binding_factory=binding_factory
        self.fixed_openings={k:float(v) for k,v in (fixed_openings or {}).items()}
        self.rain=rain
        self.ambient=dict(ambient or {})
        self.initial_input_controls={int(k):dict(v) for k,v in (initial_input_controls or {}).items()}
        self.warm_start=bool(warm_start)
        self.initial_co2_ppm={k:float(v) for k,v in (initial_co2_ppm or {}).items()}
        self.initial_openings={k:float(v) for k,v in (initial_openings or {}).items()}
        self.session=None; self._step=0; self.openings={k:self.initial_openings.get(k,0.0) for k in topology.openings}
        self.openings.update(self.fixed_openings)
        missing=set(topology.zones)-set(self.zone_numbers)
        if missing: raise ValueError("missing CONTAM zone mappings: "+",".join(sorted(missing)))
        if self.initial_co2_ppm:
            missing_initial=set(topology.zones)-set(self.initial_co2_ppm)
            unknown_initial=set(self.initial_co2_ppm)-set(topology.zones)
            if missing_initial or unknown_initial:
                raise ValueError("initial CO2 mapping must exactly cover topology zones")
        unknown=set(self.opening_controls)-set(topology.openings)
        if unknown: raise ValueError("unknown opening control mappings: "+",".join(sorted(unknown)))
        fixed_unknown=set(self.fixed_openings)-set(topology.openings)
        if fixed_unknown: raise ValueError("unknown fixed openings: "+",".join(sorted(fixed_unknown)))
        overlap=set(self.opening_controls)&set(self.fixed_openings)
        if overlap: raise ValueError("opening cannot be both CONTAM-controlled and fixed: "+",".join(sorted(overlap)))

    def _observation(self):
        co2={z:co2_mass_fraction_to_ppm(self.session.zone_mass_fraction(n,self.co2_contaminant_index)) for z,n in self.zone_numbers.items()}
        flows={oid:self.session.path_flow(n) for oid,n in self.path_numbers.items()}
        return {"step":self._step,"co2_ppm":co2,"rain":self.rain,"opening_pct":dict(self.openings),"path_flow_kg_s":flows,"state_source":"contam-solved"}

    def _initial_observation(self):
        if not self.initial_co2_ppm:
            raise RuntimeError("CONTAM environment requires explicit initial_co2_ppm before the first solve")
        return {"step":0,"co2_ppm":dict(self.initial_co2_ppm),"rain":self.rain,"opening_pct":dict(self.openings),"path_flow_kg_s":{},"state_source":"prj-profile-initial"}

    def reset(self,seed=None):
        if self.session is not None: self.session.close()
        self.session=ContamXSession(self.prj_path,self.binding_factory,ambient=self.ambient,initial_input_controls=self.initial_input_controls)
        meta=self.session.setup(); self._step=0; self.openings={k:self.initial_openings.get(k,0.0) for k in self.topology.openings}; self.openings.update(self.fixed_openings)
        warm_start_steps=0
        warm_start_controls={}
        warm_start_anchor_opening_id=None
        if self.warm_start and self.opening_controls:
            # A fully symmetric all-open startup can itself be singular in
            # ContamX. Use one deterministic exterior control as the pressure
            # anchor while every other control stays at the declared snapshot
            # value. This mirrors the stable real-engine probe path.
            for opening_id in sorted(self.opening_controls):
                warm_start_controls[opening_id]=float(self.openings.get(opening_id,0.0))
            warm_start_anchor_opening_id=sorted(self.opening_controls)[0]
            anchor=self.opening_controls[warm_start_anchor_opening_id]
            if anchor.control_name:
                self.session.set_named_input_control(anchor.control_name,anchor.open_value)
            else:
                self.session.set_input_control(anchor.control_number,anchor.open_value)
            warm_start_controls[warm_start_anchor_opening_id]=100.0
            self.session.step()
            warm_start_steps=1
            for index,spec in self.initial_input_controls.items():
                self.session.set_input_control(int(index),float(spec["value"]))
        return self._initial_observation(),{"backend":"contamxpy","physics_fidelity":"CONTAM","contam":meta,"initial_state_source":"prj-profile","warm_start_steps":warm_start_steps,"warm_start_strategy":"single-anchor-open-v1" if warm_start_steps else "disabled","warm_start_anchor_opening_id":warm_start_anchor_opening_id,"warm_start_opening_pct":warm_start_controls,"restored_opening_pct":dict(self.openings)}

    def step(self,actions):
        actions=list(actions); previous=dict(self.openings)
        for action in actions:
            if action.opening_id not in self.topology.openings: raise KeyError(action.opening_id)
            if action.opening_id in self.fixed_openings:
                expected=self.fixed_openings[action.opening_id]
                if abs(float(action.target_pct)-expected)>1e-9:
                    raise RuntimeError(f"fixed CONTAM opening {action.opening_id} cannot move from {expected:.1f}% to {float(action.target_pct):.1f}%")
                self.openings[action.opening_id]=expected
                continue
            control=self.opening_controls.get(action.opening_id)
            if control is None:
                raise RuntimeError(f"opening {action.opening_id} has no CONTAM input-control mapping")
            value=control.value_for_pct(action.target_pct)
            if control.control_name:
                self.session.set_named_input_control(control.control_name,value)
            else:
                self.session.set_input_control(control.control_number,value)
            self.openings[action.opening_id]=float(action.target_pct)
        self.session.step(); self._step+=1
        obs=self._observation()
        iaq=-sum(max(0.0,v-800.0)/400.0 for v in obs["co2_ppm"].values())
        wear=-sum(abs(self.openings[k]-previous.get(k,0.0))/100.0 for k in self.openings)
        reward=RewardVector(iaq=iaq,actuator_wear=wear)
        terminated=self._step>=self.max_steps
        return obs,reward,terminated,False,{"backend":"contamxpy","physics_fidelity":"CONTAM"}

    def close(self):
        if self.session is not None: self.session.close()
