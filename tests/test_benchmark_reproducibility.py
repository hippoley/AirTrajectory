"""Reproducibility and evidence-boundary checks for toy topology benchmark."""
import unittest

from airtrajectory.benchmark import unseen_topology_benchmark


class BenchmarkReproducibilityTests(unittest.TestCase):
    def test_paired_seed_provenance_and_toy_boundary(self):
        result=unseen_topology_benchmark(train_count=3,test_count=2,horizon_steps=3,seed=17)
        contract=result["contract"]
        self.assertEqual(contract["train_seeds"],[17,18,19])
        self.assertEqual(contract["test_seeds"],[10017,10018])
        self.assertEqual(len(contract["split_sha256"]),64)
        self.assertEqual(contract["evidence_level"],"TOY_ONLY_NOT_CONTAM_OR_FIELD")
        self.assertFalse(contract["held_out_topology_families"])
        self.assertEqual(set(result["paired_vs_rule"]),{"bc","offline_q"})
        for name in ("bc","offline_q"):
            self.assertEqual(result["paired_vs_rule"][name]["n"],2)
            self.assertEqual([t.context["scenario_seed"] for t in result["trajectories"][name]],[10017,10018])
            self.assertTrue(all(t.context["benchmark_split_sha256"]==contract["split_sha256"] for t in result["trajectories"][name]))

    def test_seeds_must_not_overlap_and_bad_counts_rejected(self):
        with self.assertRaisesRegex(ValueError,"collision"):
            unseen_topology_benchmark(train_count=10001,test_count=1,horizon_steps=1,seed=0)
        for params in ({"train_count":0},{"test_count":0},{"horizon_steps":0},{"seed":-1}):
            with self.subTest(params=params):
                with self.assertRaises(ValueError):
                    unseen_topology_benchmark(**params)


if __name__ == "__main__":
    unittest.main()
