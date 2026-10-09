"""Regression: canonical objective consumes real backend toy frames, no imputation."""
import copy
import unittest

from airtrajectory.toy_ablation import same_origin_toy_ablation
from airtrajectory.toy_objective_bridge import compare_toy_episode_first_step


class ToyObjectiveBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifact = same_origin_toy_ablation(
            train_count=3, test_count=2, horizon_steps=3, seed=401,
            test_families=("hub", "loop"),
        )

    def test_five_policy_comparison_is_actual_backend_co2_only(self):
        report = compare_toy_episode_first_step(self.artifact)
        self.assertEqual(report["status"], "TOY_FIRST_STEP_DIAGNOSTIC")
        self.assertFalse(report["execution_authorized"])
        self.assertEqual(report["observed_metric_fields"], ["co2_ppm"])
        self.assertIn("pm25_ug_m3", report["unavailable_metric_fields"])
        self.assertIn("temperature_c", report["unavailable_metric_fields"])
        decision = report["decision"]
        self.assertFalse(decision["execution_authorized"])
        self.assertEqual(decision["time_grid_min"], [0.0, 1.0])
        self.assertEqual(
            {row["label"] for row in decision["results"]},
            {"HOLD", "Independent", "Rule Joint", "BC", "Offline-Q"},
        )
        self.assertEqual(
            {row["provenance"]["backend"] for row in decision["results"]},
            {"toy-scenario-v1"},
        )
        self.assertEqual(
            {row["origin_sha256"] for row in decision["results"]},
            {decision["origin_sha256"]},
        )
        self.assertEqual(
            {row["provenance"]["source_artifact_sha256"] for row in decision["results"]},
            {self.artifact["artifact_sha256"]},
        )

    def test_deterministic_across_runs(self):
        self.assertEqual(
            compare_toy_episode_first_step(self.artifact),
            compare_toy_episode_first_step(self.artifact),
        )

    def test_multiple_structural_holdout_episodes(self):
        first = compare_toy_episode_first_step(self.artifact, episode_index=0)
        second = compare_toy_episode_first_step(self.artifact, episode_index=1)
        self.assertNotEqual(first["scenario_id"], second["scenario_id"])
        self.assertNotEqual(first["origin_sha256"], second["origin_sha256"])

    def test_tampered_backend_frame_rejected_by_checksum(self):
        broken = copy.deepcopy(self.artifact)
        broken["episodes"][0]["policies"]["BC"]["frames"][0]["co2_ppm"]["room1"] = 0
        with self.assertRaisesRegex(ValueError, "disagrees with replay frames|checksum mismatch"):
            compare_toy_episode_first_step(broken)

    def test_missing_opening_kind_rejected(self):
        broken = copy.deepcopy(self.artifact)
        broken["episodes"][0]["topology"]["openings"].pop()
        # Tampering is detected before the semantic projection can run.
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            compare_toy_episode_first_step(broken)

    def test_out_of_range_episode_rejected(self):
        with self.assertRaisesRegex(ValueError, "episode_index"):
            compare_toy_episode_first_step(self.artifact, episode_index=99)


if __name__ == "__main__":
    unittest.main()
