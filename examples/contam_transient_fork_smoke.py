"""Run a real ContamX transient counterfactual smoke from generated PRJ provenance."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.contam import ContamControl
from airtrajectory.contam_fork import ContamForkProfile, contam_strategy_fork_request
from airtrajectory.demo_runtime import DemoRuntimeSnapshot
from airtrajectory.layout import LayoutContract


ROOT=Path(__file__).resolve().parents[1]


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("prj",type=Path)
    parser.add_argument("provenance",type=Path)
    parser.add_argument(
        "--layout",
        type=Path,
        default=ROOT/"web"/"data"/"home_topology.fixed.json",
    )
    args=parser.parse_args()

    provenance=json.loads(args.provenance.read_text(encoding="utf-8"))
    if provenance.get("contaminant_simulation_mode")!="transient":
        raise RuntimeError("generated PRJ is not transient contaminant mode")

    layout=LayoutContract.from_file(args.layout)
    topology=layout.to_building_topology()
    snapshot=DemoRuntimeSnapshot.resolve(layout)

    zone_numbers={
        key.split(":",1)[1]:int(value)
        for key,value in provenance["zone_numbers"].items()
        if key.startswith("zone:")
    }
    path_numbers={
        key.split(":",1)[1]:int(value)
        for key,value in provenance["path_numbers"].items()
        if key.startswith("path:")
    }
    controls={}
    for opening_id,name in (provenance.get("input_control_names") or {}).items():
        bounds=(provenance.get("input_control_ranges") or {}).get(opening_id) or {}
        controls[opening_id]=ContamControl(
            control_name=name,
            closed_value=float(bounds.get("closed_value",0.0)),
            open_value=float(bounds.get("open_value",1.0)),
        )

    fixed={
        opening_id:float(snapshot.opening_states[opening_id])
        for opening_id in topology.openings
        if opening_id not in controls
    }
    initial_co2={
        key:float(value)
        for key,value in provenance["initial_co2_ppm"].items()
    }
    origin_openings={
        opening_id:float(snapshot.opening_states[opening_id])
        for opening_id in topology.openings
    }

    profile=ContamForkProfile(
        "transient-demo-v1",
        topology,
        args.prj,
        zone_numbers,
        controls,
        path_numbers=path_numbers,
        fixed_openings=fixed,
        ambient=dict(provenance.get("contam_ambient") or {}),
        initial_input_controls={
            int(index):dict(spec)
            for index,spec in (provenance.get("initial_input_controls") or {}).items()
        },
        evaluation_zone="living",
        evidence_level="real-contam-transient-demo",
        trusted_for_promotion=False,
        prj_initial_co2_ppm=initial_co2,
        origin_state_mode="prj-initial-only",
    )

    response=contam_strategy_fork_request(
        {
            "profile_id":"transient-demo-v1",
            "origin":{
                "co2_ppm":initial_co2,
                "opening_pct":origin_openings,
                "scalar_values":{},
            },
            "candidates":[
                {"label":"W1-55","actions":[{"opening_id":"W1","target_pct":55}]},
                {"label":"W2-55","actions":[{"opening_id":"W2","target_pct":55}]},
                {"label":"W3-55","actions":[{"opening_id":"W3","target_pct":55}]},
            ],
            "horizon_steps":1,
            "evaluation_zone":"living",
        },
        {"transient-demo-v1":profile},
    )

    outdoor=430.0
    vectors=[
        branch["end_co2_ppm_by_zone"]
        for branch in response["branches"]
    ]
    if not vectors:
        raise RuntimeError("transient fork returned no branches")
    if any(all(abs(float(value)-outdoor)<1e-6 for value in vector.values()) for vector in vectors):
        raise RuntimeError("transient counterfactual collapsed a full zone vector to outdoor CO2 in one step")
    if not all(response.get("origin_opening_controls_applied") for _ in [0]):
        raise RuntimeError("fork opening origin was not applied")

    unique={
        tuple(round(float(vector[key]),6) for key in sorted(vector))
        for vector in vectors
    }
    if len(unique)<2:
        raise RuntimeError("transient window candidates produced indistinguishable CO2 vectors")

    payload={
        "marker":"TRANSIENT_CONTAM_COUNTERFACTUAL_EXECUTED",
        "engine_version":(response.get("contam") or {}).get("version"),
        "time_step_s":provenance.get("time_step_s"),
        "simulation_mode":provenance.get("contaminant_simulation_mode"),
        "initial_co2_ppm":initial_co2,
        "branches":response["branches"],
        "trusted_for_promotion":response.get("trusted_for_promotion"),
    }
    print(json.dumps(payload,indent=2,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
