import unittest

from airtrajectory.physics_replay import physics_fingerprint, prepare_paired_replay


def row(tid, backend, idx=0):
    return {
        "trajectory_id": tid,
        "step_index": idx,
        "is_counterfactual": False,
        "physics_provenance": {
            "backend": backend,
            "backend_version": "v1",
            "time_step_s": 60,
            "boundary_sha256": "a" * 64,
            "actuation_schema_sha256": "b" * 64,
        },
    }


class PhysicsReplayTests(unittest.TestCase):
    def test_fingerprint_requires_all_lineage(self):
        with self.assertRaisesRegex(ValueError, "missing physics_provenance"):
            physics_fingerprint({"trajectory_id": "x"})

    def test_paired_sampling_is_seeded_and_has_no_leakage(self):
        rows = [
            row("a", "contam"), row("b", "contam"),
            row("c", "toy"), row("d", "toy"),
        ]
        target = physics_fingerprint(rows[0])
        one = prepare_paired_replay(rows, target_fingerprint=target, sample_size=2, seed=7)
        two = prepare_paired_replay(rows, target_fingerprint=target, sample_size=2, seed=7)
        self.assertEqual(one, two)
        self.assertEqual(len(one["matched"]), len(one["mixed"]))
        self.assertFalse({r["trajectory_id"] for r in one["matched"]} &
                         {r["trajectory_id"] for r in one["mixed"]})

    def test_rejects_insufficient_comparable_trajectories(self):
        rows = [row("a", "contam"), row("b", "toy")]
        with self.assertRaisesRegex(ValueError, "insufficient whole-trajectory"):
            prepare_paired_replay(
                rows, target_fingerprint=physics_fingerprint(rows[0]),
                sample_size=2, seed=0,
            )

    def test_rejects_counterfactual_behavior_contamination(self):
        rows = [row("a", "contam"), row("b", "toy")]
        rows[1]["is_counterfactual"] = True
        with self.assertRaisesRegex(ValueError, "insufficient whole-trajectory"):
            prepare_paired_replay(
                rows, target_fingerprint=physics_fingerprint(rows[0]),
                sample_size=1, seed=0,
            )

    def test_rejects_mixed_lineage_within_single_trajectory(self):
        rows = [row("a", "contam", 0), row("a", "toy", 1),
                row("b", "toy")]
        with self.assertRaisesRegex(ValueError, "mixed physics inside trajectory"):
            prepare_paired_replay(
                rows, target_fingerprint=physics_fingerprint(rows[0]),
                sample_size=1, seed=0,
            )


if __name__ == "__main__":
    unittest.main()
