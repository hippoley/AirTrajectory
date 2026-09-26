"""CONTAM/contamxpy adapter.

This module wraps the real NIST Python binding when installed. Tests may inject a
binding factory, but that does not count as a real CONTAM execution.
"""
from dataclasses import dataclass
from pathlib import Path
import importlib
from typing import Callable, Dict, Optional

from .environment import VentilationEnvironment
from .trajectory import RewardVector, TransitionAction

def co2_mass_fraction_to_ppm(value: float) -> float:
    # ppmv ~= mass fraction * M_air / M_CO2 * 1e6
    return float(value) * (28.96546 / 44.0095) * 1_000_000.0

@dataclass(frozen=True)
class ContamControl:
    control_number: int
    closed_value: float = 0.0
    open_value: float = 1.0

    def value_for_pct(self,pct:float)->float:
        return self.closed_value+(self.open_value-self.closed_value)*(float(pct)/100.0)

class ContamXSession:
    """Thin lifecycle wrapper around NIST contamxpy.cxLib."""
    def __init__(self,prj_path:str|Path,binding_factory:Optional[Callable]=None,verbosity:int=0):
        self.prj_path=Path(prj_path)
        self.binding_factory=binding_factory
        self.verbosity=verbosity
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
        self.engine=factory(str(self.prj_path),0,True)
        if hasattr(self.engine,"setVerbosity"): self.engine.setVerbosity(self.verbosity)
        self.engine.setupSimulation(1)
        self.started=True
        return {
            "version":self.engine.getVersion() if hasattr(self.engine,"getVersion") else "unknown",
            "zones":getattr(self.engine,"nZones",None),
            "paths":getattr(self.engine,"nPaths",None),
            "time_step_s":self.engine.getSimTimeStep() if hasattr(self.engine,"getSimTimeStep") else None,
        }

    def _require(self,*names):
        if not self.started or self.engine is None: raise RuntimeError("CONTAM session not started")
        for name in names:
            fn=getattr(self.engine,name,None)
            if fn is not None: return fn
        raise RuntimeError("contamxpy binding missing required method: "+"/".join(names))

    def set_input_control(self,control_number:int,value:float):
        self._require("setInputControlValue")(int(control_number),float(value))

    def zone_mass_fraction(self,zone_number:int,contaminant_number:int)->float:
        return float(self._require("getZoneMassFraction","getZoneMF")(int(zone_number),int(contaminant_number)))

    def path_flow(self,path_number:int)->float:
        return float(self._require("getPathFlow")(int(path_number)))

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
        co2_contaminant_number:int=1,path_numbers:Optional[Dict[str,int]]=None,max_steps:int=120,
        binding_factory:Optional[Callable]=None,
    ):
        self.topology=topology; self.prj_path=Path(prj_path); self.zone_numbers=dict(zone_numbers)
        self.opening_controls=dict(opening_controls); self.co2_contaminant_number=co2_contaminant_number
        self.path_numbers=dict(path_numbers or {}); self.max_steps=max_steps; self.binding_factory=binding_factory
        self.session=None; self._step=0; self.openings={k:0.0 for k in topology.openings}
        missing=set(topology.zones)-set(self.zone_numbers)
        if missing: raise ValueError("missing CONTAM zone mappings: "+",".join(sorted(missing)))
        unknown=set(self.opening_controls)-set(topology.openings)
        if unknown: raise ValueError("unknown opening control mappings: "+",".join(sorted(unknown)))

    def _observation(self):
        co2={z:co2_mass_fraction_to_ppm(self.session.zone_mass_fraction(n,self.co2_contaminant_number)) for z,n in self.zone_numbers.items()}
        flows={oid:self.session.path_flow(n) for oid,n in self.path_numbers.items()}
        return {"step":self._step,"co2_ppm":co2,"opening_pct":dict(self.openings),"path_flow_kg_s":flows}

    def reset(self,seed=None):
        if self.session is not None: self.session.close()
        self.session=ContamXSession(self.prj_path,self.binding_factory)
        meta=self.session.setup(); self._step=0; self.openings={k:0.0 for k in self.topology.openings}
        return self._observation(),{"backend":"contamxpy","physics_fidelity":"CONTAM","contam":meta}

    def step(self,actions):
        actions=list(actions); previous=dict(self.openings)
        for action in actions:
            if action.opening_id not in self.topology.openings: raise KeyError(action.opening_id)
            control=self.opening_controls.get(action.opening_id)
            if control is None:
                raise RuntimeError(f"opening {action.opening_id} has no CONTAM input-control mapping")
            self.session.set_input_control(control.control_number,control.value_for_pct(action.target_pct))
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
