"""Generate the static Episode Lab artifact from the real Python experiment loop."""
import json
from pathlib import Path
from airtrajectory.benchmark import unseen_topology_benchmark

def compact_trajectory(t):
    return {
        "id":t.id,
        "topology_id":t.topology_id,
        "policy_id":t.policy_id,
        "return":t.return_value,
        "context":t.context,
        "steps":[{
            "index":s.index,
            "observation":s.observation,
            "proposed_actions":[{"opening_id":a.opening_id,"target_pct":a.target_pct} for a in s.proposed_actions],
            "executed_actions":[{"opening_id":a.opening_id,"target_pct":a.target_pct} for a in s.executed_actions],
            "reward":{
                "iaq":s.reward.iaq,"comfort":s.reward.comfort,"energy":s.reward.energy,
                "safety":s.reward.safety,"actuator_wear":s.reward.actuator_wear,
                "override":s.reward.override,"scalar":s.reward.scalar(),
            },
            "next_observation":s.next_observation,
        } for s in t.steps],
    }

def main():
    result=unseen_topology_benchmark(train_count=18,test_count=3,horizon_steps=20,seed=2609)
    payload={
        "schema_version":"0.1",
        "generated_by":"airtrajectory.benchmark.unseen_topology_benchmark",
        "provenance":"backend-generated · toy-scenario-v1 · not engineering truth",
        "contract":result["contract"],
        "metrics":result["metrics"],
        "episode":{
            name:compact_trajectory(result["trajectories"][name][0])
            for name in ("rule","bc","offline_q")
        },
    }
    path=Path("web/data/experiment.json")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print("wrote",path)

if __name__=="__main__":
    main()
