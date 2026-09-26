"""Trajectory factory for reproducible multi-topology experiments."""
from .agents import MultiWindowRuleAgent
from .environment import ScenarioMultizoneEnvironment
from .rollout import rollout
from .physical import SafetyResolver
from .scenario import generate_chain_scenario, topology_manifest

class TrajectoryFactory:
    def __init__(self,horizon_steps=120,rooms=(2,3,4,5)):
        self.horizon_steps=horizon_steps
        self.rooms=tuple(rooms)

    def rule_episode(self,seed:int):
        room_count=self.rooms[seed % len(self.rooms)]
        scenario=generate_chain_scenario(seed,room_count)
        env=ScenarioMultizoneEnvironment(scenario,horizon_steps=self.horizon_steps)
        agent=MultiWindowRuleAgent(scenario.topology)
        trajectory=rollout(env,agent,scenario.id,"multi-window-rule-v1",max_steps=self.horizon_steps,safety_resolver=SafetyResolver())
        trajectory.context.update({
            "scenario_seed":seed,
            "room_count":room_count,
            "occupancy":scenario.occupancy,
            "rain":scenario.rain,
            "outdoor_temp_c":scenario.outdoor_temp_c,
            "physics_fidelity":"toy",
            "topology":topology_manifest(scenario.topology),
        })
        return trajectory

    def generate_rule_episodes(self,count:int,seed:int=0):
        if count < 1: raise ValueError("count must be >= 1")
        return [self.rule_episode(seed+i) for i in range(count)]
