"""Unseen-topology benchmark: train on 2–4 rooms, test on 5-room homes."""
from statistics import mean
from hashlib import sha256
import json
from .agents import MultiWindowRuleAgent
from .dataset import transition_rows
from .environment import ScenarioMultizoneEnvironment
from .factory import TrajectoryFactory
from .learning import TopologyBCPolicy, TopologyOfflineQPolicy
from .rollout import rollout
from .physical import SafetyResolver
from .scenario import generate_chain_scenario, generate_structured_scenario, topology_manifest

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

def _paired_deltas(results, baseline="rule"):
    """Episode-paired deltas; all policies are evaluated on identical seeds."""
    reference=results[baseline]
    deltas={}
    for name, trajectories in results.items():
        if name == baseline: continue
        if len(trajectories) != len(reference):
            raise ValueError("paired benchmark length mismatch")
        differences=[candidate.return_value - control.return_value
                     for candidate, control in zip(trajectories,reference)]
        deltas[name]={"baseline":baseline,"n":len(differences),
                      "mean_return_delta":mean(differences),
                      "positive_episode_fraction":sum(d>0 for d in differences)/len(differences)}
    return deltas


def unseen_topology_benchmark(train_count=24,test_count=8,horizon_steps=30,seed=100):
    if not all(isinstance(v,int) and not isinstance(v,bool) and v>0
               for v in (train_count,test_count,horizon_steps)):
        raise ValueError("train_count, test_count and horizon_steps must be positive integers")
    if not isinstance(seed,int) or isinstance(seed,bool) or seed<0:
        raise ValueError("seed must be a non-negative integer")
    train_seeds=[seed+i for i in range(train_count)]
    test_seeds=[seed+10000+i for i in range(test_count)]
    if set(train_seeds) & set(test_seeds):
        raise ValueError("train/test random seed collision")
    split={"schema_version":"0.1","train_seeds":train_seeds,
           "test_seeds":test_seeds,"train_rooms":[2,3,4],"test_rooms":[5],
           "topology_family":"chain","backend":"toy-scenario-v1"}
    split_hash=sha256(json.dumps(split,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    train_factory=TrajectoryFactory(horizon_steps=horizon_steps,rooms=(2,3,4))
    train=[train_factory.rule_episode(seed+i) for i in range(train_count)]
    rows=_rows(train)
    bc=TopologyBCPolicy(); bc.fit(rows)
    offline=TopologyOfflineQPolicy(); offline.fit(rows)
    results={"rule":[],"bc":[],"offline_q":[]}
    for test_seed in test_seeds:
        s=generate_chain_scenario(test_seed,rooms=5)
        policies={
            "rule":MultiWindowRuleAgent(s.topology),
            "bc":bc,
            "offline_q":offline,
        }
        for name,policy in policies.items():
            env=ScenarioMultizoneEnvironment(s,horizon_steps=horizon_steps)
            t=rollout(env,policy,s.id,name,max_steps=horizon_steps,safety_resolver=SafetyResolver())
            t.context.update({"benchmark_split":"unseen-topology","room_count":5,"physics_fidelity":"toy","scenario_seed":test_seed,"benchmark_split_sha256":split_hash,"topology":topology_manifest(s.topology)})
            results[name].append(t)
    return {
        "contract":{**split,"split_sha256":split_hash,"evidence_level":"TOY_ONLY_NOT_CONTAM_OR_FIELD","held_out_topology_families":False},
        "paired_vs_rule":_paired_deltas(results),
        "metrics":{k:_summary(v) for k,v in results.items()},
        "trajectories":results,
    }


def held_out_family_benchmark(train_count=24, test_count_per_family=8, horizon_steps=30, seed=100):
    """Evaluate chain-trained policies on disjoint hub/loop/branch graph families.

    This measures toy-environment topology-family transfer only; it does not
    establish ContamX validity, real building transfer, or physical safety.
    """
    if any(not isinstance(v,int) or isinstance(v,bool) or v<=0
           for v in (train_count,test_count_per_family,horizon_steps)):
        raise ValueError("counts and horizon_steps must be positive integers")
    if not isinstance(seed,int) or isinstance(seed,bool) or seed<0:
        raise ValueError("seed must be a non-negative integer")
    train_seeds=[seed+i for i in range(train_count)]
    test_seeds=[seed+10000+i for i in range(test_count_per_family)]
    if set(train_seeds)&set(test_seeds):
        raise ValueError("train/test seed collision")
    train_factory=TrajectoryFactory(horizon_steps=horizon_steps,rooms=(2,3,4))
    train=[train_factory.rule_episode(i) for i in train_seeds]
    rows=_rows(train)
    bc=TopologyBCPolicy(); bc.fit(rows)
    offline=TopologyOfflineQPolicy(); offline.fit(rows)
    families=("hub","loop","branch")
    split={"schema_version":"0.1","train_families":["chain"],
           "test_families":list(families),"train_rooms":[2,3,4],
           "test_rooms":[5],"train_seeds":train_seeds,
           "test_seeds":test_seeds,"backend":"toy-scenario-v1"}
    split_hash=sha256(json.dumps(split,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    by_family={}
    for family in families:
        result={"rule":[],"bc":[],"offline_q":[]}
        for test_seed in test_seeds:
            scenario=generate_structured_scenario(test_seed,rooms=5,family=family)
            for policy_name,policy in (
                ("rule", MultiWindowRuleAgent(scenario.topology)),
                ("bc",bc),("offline_q",offline),
            ):
                env=ScenarioMultizoneEnvironment(scenario,horizon_steps=horizon_steps)
                episode=rollout(env,policy,scenario.id,policy_name,
                                max_steps=horizon_steps,safety_resolver=SafetyResolver())
                episode.context.update({
                    "benchmark_split":"held-out-graph-family",
                    "benchmark_split_sha256":split_hash,"scenario_seed":test_seed,
                    "room_count":5,"topology_family":family,"physics_fidelity":"toy",
                    "topology":topology_manifest(scenario.topology),
                })
                result[policy_name].append(episode)
        by_family[family]={"metrics":{name:_summary(episodes) for name,episodes in result.items()},
                           "paired_vs_rule":_paired_deltas(result),
                           "trajectories":result}
    return {"contract":{**split,"split_sha256":split_hash,
                        "evidence_level":"TOY_ONLY_NOT_CONTAM_OR_FIELD",
                        "held_out_topology_families":True},
            "by_family":by_family}
