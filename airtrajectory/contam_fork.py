"""CONTAM-backed counterfactual fork contract.

Each candidate is evaluated from a fresh CONTAMEnvironment constructed from the
same explicit origin snapshot. This avoids branch state leakage and keeps the
counterfactual provenance separate from the fast toy backend.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from .contam import CONTAMEnvironment, ContamControl, ContamScalarControl
from .trajectory import TransitionAction, ScalarControlAction


@dataclass(frozen=True)
class ContamForkProfile:
    profile_id: str
    topology: Any
    prj_path: str | Path
    zone_numbers: Mapping[str, int]
    opening_controls: Mapping[str, ContamControl]
    path_numbers: Mapping[str, int] = field(default_factory=dict)
    fixed_openings: Mapping[str, float] = field(default_factory=dict)
    ambient: Mapping[str, Any] = field(default_factory=dict)
    initial_input_controls: Mapping[int, dict] = field(default_factory=dict)
    scalar_controls: Mapping[str, ContamScalarControl] = field(default_factory=dict)
    co2_contaminant_index: int = 0
    evaluation_zone: str = "living"


def _validate_origin(profile: ContamForkProfile, origin: dict) -> tuple[dict, dict, dict]:
    co2=origin.get("co2_ppm")
    openings=origin.get("opening_pct")
    scalars=origin.get("scalar_values",{})
    if not isinstance(co2,dict) or not isinstance(openings,dict) or not isinstance(scalars,dict):
        raise ValueError("CONTAM fork origin requires co2_ppm/opening_pct mappings and scalar_values when configured")
    zones=set(profile.topology.zones)
    opening_ids=set(profile.topology.openings)
    scalar_ids=set(profile.scalar_controls)
    if set(co2)!=zones:
        raise ValueError("CONTAM fork co2_ppm must exactly cover profile zones")
    if set(openings)!=opening_ids:
        raise ValueError("CONTAM fork opening_pct must exactly cover profile openings")
    if set(scalars)!=scalar_ids:
        raise ValueError("CONTAM fork scalar_values must exactly cover profile scalar controls")
    return (
        {k:float(v) for k,v in co2.items()},
        {k:float(v) for k,v in openings.items()},
        {k:float(v) for k,v in scalars.items()},
    )


def _normalize_actions(profile: ContamForkProfile, actions) -> list:
    if not isinstance(actions,list) or not actions:
        raise ValueError("CONTAM strategy branch actions must be a non-empty list")
    out=[]
    seen=set()
    for raw in actions:
        if not isinstance(raw,dict):
            raise ValueError("CONTAM strategy action must be an object")
        has_opening="opening_id" in raw
        has_scalar="actuator_id" in raw
        if has_opening==has_scalar:
            raise ValueError("CONTAM strategy action must specify exactly one of opening_id or actuator_id")
        if has_opening:
            opening_id=str(raw.get("opening_id",""))
            if opening_id not in profile.topology.openings:
                raise ValueError("unknown CONTAM opening_id: "+opening_id)
            if opening_id in profile.fixed_openings:
                raise ValueError("CONTAM strategy cannot vary fixed opening: "+opening_id)
            key=("opening",opening_id)
            if key in seen:
                raise ValueError("CONTAM strategy contains duplicate opening_id: "+opening_id)
            seen.add(key)
            try:
                target=float(raw["target_pct"])
            except (KeyError,TypeError,ValueError):
                raise ValueError("CONTAM opening action requires numeric target_pct")
            if target<0 or target>100:
                raise ValueError("CONTAM strategy target_pct out of range")
            out.append(TransitionAction(opening_id,target))
            continue
        actuator_id=str(raw.get("actuator_id",""))
        control=profile.scalar_controls.get(actuator_id)
        if control is None:
            raise ValueError("unknown CONTAM scalar actuator_id: "+actuator_id)
        key=("scalar",actuator_id)
        if key in seen:
            raise ValueError("CONTAM strategy contains duplicate actuator_id: "+actuator_id)
        seen.add(key)
        try:
            target=float(raw["target_value"])
        except (KeyError,TypeError,ValueError):
            raise ValueError("CONTAM scalar action requires numeric target_value")
        control.value_for_command(target)
        out.append(ScalarControlAction(actuator_id,target))
    return out


def _serialize_action(action) -> dict:
    if isinstance(action,TransitionAction):
        return {"kind":"opening","opening_id":action.opening_id,"target_pct":float(action.target_pct)}
    if isinstance(action,ScalarControlAction):
        return {"kind":"scalar","actuator_id":action.actuator_id,"target_value":float(action.target_value)}
    raise TypeError("unsupported normalized CONTAM action type: "+type(action).__name__)


def _run_actions_branch(
    profile: ContamForkProfile,
    origin_co2: dict,
    origin_openings: dict,
    origin_scalars: dict,
    actions,
    horizon_steps: int,
    binding_factory=None,
):
    env=CONTAMEnvironment(
        profile.topology,
        profile.prj_path,
        dict(profile.zone_numbers),
        dict(profile.opening_controls),
        co2_contaminant_index=profile.co2_contaminant_index,
        path_numbers=dict(profile.path_numbers),
        max_steps=max(1,int(horizon_steps)),
        binding_factory=binding_factory,
        fixed_openings=dict(profile.fixed_openings),
        initial_openings=dict(origin_openings),
        initial_co2_ppm=dict(origin_co2),
        ambient=dict(profile.ambient),
        initial_input_controls=dict(profile.initial_input_controls),
        scalar_controls=dict(profile.scalar_controls),
        initial_scalar_values=dict(origin_scalars),
    )
    observations=[]
    total_return=0.0
    try:
        _,meta=env.reset()
        normalized=_normalize_actions(profile,actions)
        for _ in range(max(1,int(horizon_steps))):
            obs,reward,done,truncated,_=env.step(normalized)
            observations.append(obs)
            total_return+=reward.scalar()
            if done or truncated:
                break
    finally:
        env.close()
    if not observations:
        raise RuntimeError("CONTAM fork produced no solved observations")
    return observations,total_return,meta


def contam_fork_request(
    payload: Dict[str, Any],
    profiles: Mapping[str, ContamForkProfile],
    binding_factory=None,
) -> Dict[str, Any]:
    required=("profile_id","opening_id","origin")
    missing=[k for k in required if k not in payload]
    if missing:
        raise ValueError("missing CONTAM fork request fields: "+",".join(missing))
    profile_id=str(payload["profile_id"])
    profile=profiles.get(profile_id)
    if profile is None:
        raise ValueError("unknown CONTAM profile_id: "+profile_id)
    opening_id=str(payload["opening_id"])
    if opening_id not in profile.topology.openings:
        raise ValueError("unknown CONTAM opening_id: "+opening_id)
    if opening_id in profile.fixed_openings:
        raise ValueError("CONTAM fork cannot vary fixed opening: "+opening_id)

    origin_co2,origin_openings,origin_scalars=_validate_origin(profile,payload["origin"])
    levels=payload.get("levels",[0,25,50,75,100])
    if not isinstance(levels,list) or not levels:
        raise ValueError("CONTAM fork levels must be a non-empty list")
    horizon_steps=max(1,int(payload.get("horizon_steps",payload.get("horizon_minutes",30))))
    evaluation_zone=str(payload.get("evaluation_zone") or profile.evaluation_zone)
    if evaluation_zone not in profile.topology.zones:
        raise ValueError("unknown CONTAM evaluation_zone: "+evaluation_zone)

    branches=[]
    meta=None
    for raw in levels:
        target=float(raw)
        observations,total_return,branch_meta=_run_actions_branch(
            profile,origin_co2,origin_openings,origin_scalars,
            [{"opening_id":opening_id,"target_pct":target}],
            horizon_steps,binding_factory
        )
        meta=meta or branch_meta
        final=observations[-1]
        branches.append({
            "label":"CLOSE" if target==0 else "OPEN100" if target==100 else f"VENT{int(target) if target.is_integer() else target}",
            "target_pct":target,
            "end_co2_ppm":round(float(final["co2_ppm"][evaluation_zone]),3),
            "end_co2_ppm_by_zone":{k:round(float(v),3) for k,v in final["co2_ppm"].items()},
            "path_flow_kg_s":dict(final.get("path_flow_kg_s") or {}),
            "end_scalar_values":dict(final.get("scalar_values") or {}),
            "series":[round(float(x["co2_ppm"][evaluation_zone]),3) for x in observations],
            "return":round(float(total_return),6),
            "provenance":"backend-generated · CONTAM · engineering simulation",
            "trusted_for_promotion":True,
        })

    return {
        "schema_version":"0.2",
        "request_id":str(payload.get("request_id","")),
        "profile_id":profile_id,
        "topology_id":str(payload.get("topology_id",profile_id)),
        "opening_id":opening_id,
        "origin_kind":"explicit-snapshot",
        "backend":"contamxpy",
        "physics_fidelity":"CONTAM",
        "trusted_for_promotion":True,
        "horizon_minutes":horizon_steps,
        "contam":meta.get("contam") if isinstance(meta,dict) else None,
        "branches":branches,
    }


def contam_strategy_fork_request(
    payload: Dict[str, Any],
    profiles: Mapping[str, ContamForkProfile],
    binding_factory=None,
) -> Dict[str, Any]:
    required=("profile_id","origin","candidates")
    missing=[k for k in required if k not in payload]
    if missing:
        raise ValueError("missing CONTAM strategy fork fields: "+",".join(missing))
    profile_id=str(payload["profile_id"])
    profile=profiles.get(profile_id)
    if profile is None:
        raise ValueError("unknown CONTAM profile_id: "+profile_id)
    origin_co2,origin_openings,origin_scalars=_validate_origin(profile,payload["origin"])
    candidates=payload["candidates"]
    if not isinstance(candidates,list) or not candidates:
        raise ValueError("CONTAM strategy candidates must be a non-empty list")
    horizon_steps=max(1,int(payload.get("horizon_steps",payload.get("horizon_minutes",30))))
    evaluation_zone=str(payload.get("evaluation_zone") or profile.evaluation_zone)
    if evaluation_zone not in profile.topology.zones:
        raise ValueError("unknown CONTAM evaluation_zone: "+evaluation_zone)

    labels=set()
    branches=[]
    meta=None
    for index,candidate in enumerate(candidates):
        if not isinstance(candidate,dict):
            raise ValueError("CONTAM strategy candidate must be an object")
        label=str(candidate.get("label") or f"strategy-{index+1}")
        if label in labels:
            raise ValueError("duplicate CONTAM strategy label: "+label)
        labels.add(label)
        actions=candidate.get("actions")
        normalized=_normalize_actions(profile,actions)
        observations,total_return,branch_meta=_run_actions_branch(
            profile,origin_co2,origin_openings,origin_scalars,actions,horizon_steps,binding_factory
        )
        meta=meta or branch_meta
        final=observations[-1]
        branches.append({
            "label":label,
            "actions":[_serialize_action(a) for a in normalized],
            "end_co2_ppm":round(float(final["co2_ppm"][evaluation_zone]),3),
            "end_co2_ppm_by_zone":{k:round(float(v),3) for k,v in final["co2_ppm"].items()},
            "path_flow_kg_s":dict(final.get("path_flow_kg_s") or {}),
            "series":[round(float(x["co2_ppm"][evaluation_zone]),3) for x in observations],
            "return":round(float(total_return),6),
            "provenance":"backend-generated · CONTAM · engineering simulation",
            "trusted_for_promotion":True,
        })

    return {
        "schema_version":"0.4",
        "request_id":str(payload.get("request_id","")),
        "profile_id":profile_id,
        "topology_id":str(payload.get("topology_id",profile_id)),
        "origin_kind":"explicit-snapshot",
        "backend":"contamxpy",
        "physics_fidelity":"CONTAM",
        "trusted_for_promotion":True,
        "horizon_minutes":horizon_steps,
        "contam":meta.get("contam") if isinstance(meta,dict) else None,
        "branches":branches,
    }
