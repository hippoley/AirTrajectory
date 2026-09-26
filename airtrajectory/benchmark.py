"""Unseen-topology benchmark: train on 2–4 rooms, test on 5-room homes."""
from statistics import mean
from .agents import MultiWindowRuleAgent
from .dataset import transition_rows
from .environment import ScenarioMultizoneEnvironment
from .factory import TrajectoryFactory
from .learning import TopologyBCPolicy, TopologyOfflineQPolicy
from .rollout import rollout
from .physical import SafetyResolver
from .scenario import generate_chain_scenario, topology_manifest

def _rows(trajectories):
    out=[]
    for t in trajectories: out.extend(transition_rows(t))
    return out

def _summary(trajectories):
    returns=[t.return_value for t in trajectories]
    final_max=[max(t.steps[-1].next_observation["co2_ppm"].values()) for t in trajectories]
    safety_steps=sum(1 for t in trajectories for s in t.steps if s.reward.safety < 0)
    interventions=sum(1 for t in trajectories for s in t.steps if s.intervention)
    return {
        "episodes":len(trajectories),
        "mean_return":mean(returns),
        "mean_final_max_co2_ppm":mean(final_max),
        "safety_violation_steps":safety_steps,
        "safety_intervention_steps":interventions,
    }

def unseen_topology_benchmark(train_count=24,test_count=8,horizon_steps=30,seed=100):
    train_factory=TrajectoryFactory(horizon_steps=horizon_steps,rooms=(2,3,4))
    train=[train_factory.rule_episode(seed+i) for i in range(train_count)]
    rows=_rows(train)
    bc=TopologyBCPolicy(); bc.fit(rows)
    offline=TopologyOfflineQPolicy(); offline.fit(rows)
    results={"rule":[],"bc":[],"offline_q":[]}
    for i in range(test_count):
        s=generate_chain_scenario(seed+10000+i,rooms=5)
        policies={
            "rule":MultiWindowRuleAgent(s.topology),
            "bc":bc,
            "offline_q":offline,
        }
        for name,policy in policies.items():
            env=ScenarioMultizoneEnvironment(s,horizon_steps=horizon_steps)
            t=rollout(env,policy,s.id,name,max_steps=horizon_steps,safety_resolver=SafetyResolver())
            t.context.update({"benchmark_split":"unseen-topology","room_count":5,"physics_fidelity":"toy","topology":topology_manifest(s.topology)})
            results[name].append(t)
    return {
        "contract":{"train_rooms":[2,3,4],"test_rooms":[5],"backend":"toy-scenario-v1"},
        "metrics":{k:_summary(v) for k,v in results.items()},
        "trajectories":results,
    }
