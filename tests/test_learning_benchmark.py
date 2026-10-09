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
        self.assertEqual(result["contract"]["train_seeds"],[55,56,57,58,59,60])
        self.assertEqual(result["contract"]["test_seeds"],[10055,10056])
        self.assertFalse(set(result["contract"]["train_seeds"]) & set(result["contract"]["test_seeds"]))
        self.assertTrue(result["contract"]["same_test_origin_across_policies"])
        self.assertEqual(set(result["metrics"]),{"rule","bc","offline_q"})
        self.assertTrue(all(m["episodes"]==2 for m in result["metrics"].values()))

    def test_benchmark_rejects_invalid_split_and_bogus_counts(self):
        for kwargs in (
            {"train_count":0}, {"test_count":0}, {"horizon_steps":0},
            {"train_count":True}, {"test_count":1.5},
            {"seed":-1}, {"seed":True},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    unseen_topology_benchmark(**kwargs)
        # Intentionally collide the training range with test seed 10000.
        # Rejection must happen BEFORE expensive episode generation.
        with self.assertRaisesRegex(ValueError, "overlap"):
            unseen_topology_benchmark(train_count=10001, test_count=1, seed=0)

if __name__=="__main__":
    unittest.main()
