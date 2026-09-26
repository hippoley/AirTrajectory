"""Transport-neutral counterfactual fork contract.

No web framework dependency: adapters can expose fork_request() over HTTP, MQTT,
a local process, or tests without changing the simulation contract.
"""
from dataclasses import dataclass
from typing import Any, Dict

from .environment import ToyMultizoneEnvironment
from .fork import fork_window_levels
from .topology import BuildingTopology, OpeningEdge, ZoneNode
from .telemetry import DecisionTelemetry


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


def fork_request(payload: Dict[str, Any], telemetry: DecisionTelemetry | None = None) -> Dict[str, Any]:
    req=ForkRequest.from_dict(payload)
    telemetry=telemetry or DecisionTelemetry()
    with telemetry.span("counterfactual.fork", request_id=req.request_id, topology_id=req.topology_id, opening_id=req.opening_id, horizon_minutes=req.horizon_minutes) as decision_trace:
        return _fork_request(req, decision_trace)

def _fork_request(req: ForkRequest, decision_trace) -> Dict[str, Any]:
    if req.topology_id!="demo-3zone":
        raise ValueError("unsupported topology_id; arbitrary topology transport is not implemented yet")
    topology=demo_topology()
    co2=req.origin["co2_ppm"]
    supplied=req.origin["opening_pct"]
    if not isinstance(co2,dict) or not isinstance(supplied,dict):
        raise ValueError("demo-3zone origin requires complete co2_ppm and opening_pct mappings")
    required_zones=set(topology.zones)
    required_openings=set(topology.openings)
    missing_zones=required_zones-set(co2)
    missing_openings=required_openings-set(supplied)
    extra_zones=set(co2)-required_zones
    extra_openings=set(supplied)-required_openings
    if missing_zones or missing_openings or extra_zones or extra_openings:
        detail=[]
        if missing_zones: detail.append("missing zones="+",".join(sorted(missing_zones)))
        if missing_openings: detail.append("missing openings="+",".join(sorted(missing_openings)))
        if extra_zones: detail.append("unknown zones="+",".join(sorted(extra_zones)))
        if extra_openings: detail.append("unknown openings="+",".join(sorted(extra_openings)))
        raise ValueError("incomplete demo-3zone origin: "+"; ".join(detail))
    env=ToyMultizoneEnvironment(topology,{k:float(v) for k,v in co2.items()},dt_minutes=1,horizon_steps=max(60,req.horizon_minutes+1))
    env.reset()
    snapshot=env.snapshot()
    snapshot["co2"]={k:float(v) for k,v in co2.items()}
    for key,value in supplied.items():
        snapshot["openings"][key]=float(value)
    env.restore(snapshot)
    decision_trace.attributes["origin.co2_ppm"]=co2
    decision_trace.attributes["origin.opening_pct"]=supplied
    branches=fork_window_levels(env,req.opening_id,horizon_steps=req.horizon_minutes)
    decision_trace.attributes["branch.count"]=len(branches)
    decision_trace.events.extend({"name":"branch.result","label":label,"target_pct":branch.actions[0].target_pct,"return":round(branch.return_value,3)} for label,branch in branches.items())
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
