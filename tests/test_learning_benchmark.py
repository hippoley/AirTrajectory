import unittest
from airtrajectory.dataset import transition_rows
from airtrajectory.factory import TrajectoryFactory
from airtrajectory.learning import TopologyBCPolicy, TopologyOfflineQPolicy
from airtrajectory.benchmark import unseen_topology_benchmark

class LearningBenchmarkTests(unittest.TestCase):
    def _rows(self):
        ts=TrajectoryFactory(horizon_steps=4,rooms=(2,3,4)).generate_rule_episodes(6,seed=40)
        return [row for t in ts for row in transition_rows(t)]

    def test_topology_bc_emits_actions_for_unseen_window_ids(self):
        bc=TopologyBCPolicy(); bc.fit(self._rows())
        t=TrajectoryFactory(horizon_steps=1,rooms=(5,)).rule_episode(999)
        obs=t.steps[0].observation
        actions=bc(obs)
        self.assertEqual({a.opening_id for a in actions},set(obs["opening_zone"])|set(obs["interior_openings"]))
        self.assertTrue(all(a.target_pct in (0,25,50,75,100) for a in actions))

    def test_topology_offline_q_never_invents_action_outside_support(self):
        q=TopologyOfflineQPolicy(); q.fit(self._rows())
        t=TrajectoryFactory(horizon_steps=1,rooms=(5,)).rule_episode(1001)
        obs=t.steps[0].observation
        actions=q(obs)
        self.assertEqual(len(actions),len(obs["opening_zone"])+len(obs["interior_openings"]))
        self.assertTrue(all(a.target_pct in (0,25,50,75,100) for a in actions))

    def test_benchmark_holds_out_room_count(self):
        result=unseen_topology_benchmark(train_count=6,test_count=2,horizon_steps=4,seed=55)
        self.assertEqual(result["contract"]["train_rooms"],[2,3,4])
        self.assertEqual(result["contract"]["test_rooms"],[5])
        self.assertEqual(set(result["metrics"]),{"rule","bc","offline_q"})
        self.assertTrue(all(m["episodes"]==2 for m in result["metrics"].values()))

if __name__=="__main__":
    unittest.main()
