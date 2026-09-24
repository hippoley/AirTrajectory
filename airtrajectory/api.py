"""Transport-neutral counterfactual fork contract.

No web framework dependency: adapters can expose fork_request() over HTTP, MQTT,
a local process, or tests without changing the simulation contract.
"""
from dataclasses import dataclass
from typing import Any, Dict

from .environment import ToyMultizoneEnvironment
from .fork import fork_window_levels
from .topology import BuildingTopology, OpeningEdge, ZoneNode


@dataclass(frozen=True)
class ForkRequest:
    topology_id: str
    opening_id: str
    origin: Dict[str, Any]
    horizon_minutes: int = 30
    request_id: str = ""

    @classmethod
    def from_dict(cls, payload):
        required=("topology_id","opening_id","origin")
        missing=[k for k in required if k not in payload]
        if missing: raise ValueError("missing fork request fields: "+",".join(missing))
        origin=payload["origin"]
        if "co2_ppm" not in origin or "opening_pct" not in origin:
            raise ValueError("origin requires co2_ppm and opening_pct")
        return cls(payload["topology_id"],payload["opening_id"],origin,int(payload.get("horizon_minutes",30)),str(payload.get("request_id","")))


def demo_topology():
    return BuildingTopology.from_parts(
        [ZoneNode("living",45),ZoneNode("bedroom",30),ZoneNode("study",22)],
        [OpeningEdge("W1","living","OUTSIDE","window",1.2),OpeningEdge("W2","bedroom","OUTSIDE","window",1.0),
         OpeningEdge("W3","study","OUTSIDE","window",.9),OpeningEdge("D1","living","bedroom","door",1.8),
         OpeningEdge("D2","living","study","door",1.4)])


def fork_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    req=ForkRequest.from_dict(payload)
    if req.topology_id!="demo-3zone":
        raise ValueError("unsupported topology_id; arbitrary topology transport is not implemented yet")
    topology=demo_topology()
    co2=req.origin["co2_ppm"]
    if isinstance(co2,(int,float)):
        co2={"living":float(co2),"bedroom":980.0,"study":840.0}
    env=ToyMultizoneEnvironment(topology,co2,dt_minutes=1,horizon_steps=max(60,req.horizon_minutes+1))
    env.reset()
    snapshot=env.snapshot()
    snapshot["co2"]={k:float(v) for k,v in co2.items()}
    supplied=req.origin["opening_pct"]
    if isinstance(supplied,(int,float)):
        snapshot["openings"][req.opening_id]=float(supplied)
    else:
        for key,value in supplied.items():
            if key in snapshot["openings"]: snapshot["openings"][key]=float(value)
    env.restore(snapshot)
    branches=fork_window_levels(env,req.opening_id,horizon_steps=req.horizon_minutes)
    return {
        "schema_version":"0.1","request_id":req.request_id,"topology_id":req.topology_id,
        "origin_kind":"post-action-snapshot","backend":"toy-multizone-v1","horizon_minutes":req.horizon_minutes,
        "branches":[{
            "label":label,"target_pct":branch.actions[0].target_pct,
            "end_co2_ppm":round(branch.observations[-1]["co2_ppm"]["living"]),
            "series":[round(o["co2_ppm"]["living"]) for o in branch.observations],
            "return":round(branch.return_value,3),
            "provenance":"backend-generated · toy-multizone-v1 · not engineering truth"
        } for label,branch in branches.items()]
    }
