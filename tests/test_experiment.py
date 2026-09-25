import unittest

from airtrajectory.agents import MultiWindowRuleAgent
from airtrajectory.environment import ScenarioMultizoneEnvironment
from airtrajectory.factory import TrajectoryFactory
from airtrajectory.judge import VentilationJudge
from airtrajectory.scenario import generate_chain_scenario


class ExperimentLoopTests(unittest.TestCase):
    def test_scenario_builds_multi_room_multi_window_topology(self):
        scenario=generate_chain_scenario(7,rooms=4)
        self.assertEqual(len(scenario.topology.zones),4)
        exterior=[
            e for e in scenario.topology.openings.values()
            if e.source==scenario.topology.outside_id or e.target==scenario.topology.outside_id
        ]
        self.assertEqual(len(exterior),4)
        self.assertEqual(len([e for e in scenario.topology.openings.values() if e.kind=="door"]),3)

    def test_agent_controls_all_windows_without_fixed_device_ids(self):
        scenario=generate_chain_scenario(11,rooms=3)
        env=ScenarioMultizoneEnvironment(scenario,horizon_steps=2)
        obs,_=env.reset()
        obs["co2_ppm"]={z:1400 for z in scenario.topology.zones}
        actions=MultiWindowRuleAgent(scenario.topology)(obs)
        exterior_ids={e.id for e in scenario.topology.openings.values() if e.kind=="window"}
        acted={a.opening_id for a in actions}
        self.assertTrue(exterior_ids.issubset(acted))
        self.assertTrue(all(a.target_pct==75 for a in actions if a.opening_id in exterior_ids))

    def test_rain_closes_every_exterior_window(self):
        scenario=generate_chain_scenario(3,rooms=3)
        object.__setattr__(scenario,"rain",True)
        env=ScenarioMultizoneEnvironment(scenario,horizon_steps=1)
        obs,_=env.reset()
        obs["co2_ppm"]={z:1600 for z in scenario.topology.zones}
        actions=MultiWindowRuleAgent(scenario.topology)(obs)
        window_ids={e.id for e in scenario.topology.openings.values() if e.kind=="window"}
        self.assertTrue(all(a.target_pct==0 for a in actions if a.opening_id in window_ids))

    def test_occupancy_source_changes_closed_room_state(self):
        scenario=generate_chain_scenario(9,rooms=2)
        object.__setattr__(scenario,"occupancy",{z:2 for z in scenario.topology.zones})
        env=ScenarioMultizoneEnvironment(scenario,horizon_steps=2)
        before,_=env.reset()
        closed=[type("A",(),{"opening_id":e.id,"target_pct":0})() for e in scenario.topology.openings.values()]
        after,_,_,_,_=env.step(closed)
        for zone in scenario.topology.zones:
            self.assertGreater(after["co2_ppm"][zone],before["co2_ppm"][zone])

    def test_factory_generates_scored_agent_trajectories(self):
        trajectories=TrajectoryFactory(horizon_steps=6,rooms=(2,3)).generate_rule_episodes(4,seed=20)
        self.assertEqual(len(trajectories),4)
        self.assertTrue(all(len(t.steps)==6 for t in trajectories))
        self.assertTrue(all(t.context["physics_fidelity"]=="toy" for t in trajectories))
        self.assertTrue(all(len(t.steps[0].executed_actions)>=3 for t in trajectories))
        self.assertTrue(all(isinstance(t.return_value,float) for t in trajectories))


if __name__=="__main__":
    unittest.main()
