"""Regression tests for reproducible, evidence-limited learning ablations."""
import copy
import unittest

from airtrajectory.toy_ablation import (
    IndependentWindowPolicy,
    same_origin_toy_ablation,
    verify_toy_ablation,
)


class ToyAblationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifact = same_origin_toy_ablation(
            train_count=4, test_count=2, horizon_steps=4, seed=80
        )

    def test_all_five_policies_replay_same_origin_and_horizon(self):
        payload = self.artifact
        self.assertTrue(verify_toy_ablation(payload))
        self.assertEqual(
            set(payload["evaluation"]["policies"]),
            {"HOLD", "Independent", "Rule Joint", "BC", "Offline-Q"},
        )
        for episode in payload["episodes"]:
            self.assertEqual(
                len({r["origin_sha256"] for r in episode["policies"].values()}),
                1,
            )
            self.assertEqual(
                {len(r["frames"]) for r in episode["policies"].values()},
                {4},
            )
            self.assertEqual(
                {r["physics_backend"] for r in episode["policies"].values()},
                {"toy-scenario-v1"},
            )

    def test_hold_really_keeps_all_openings_unchanged(self):
        for episode in self.artifact["episodes"]:
            hold = episode["policies"]["HOLD"]
            for frame in hold["frames"]:
                self.assertEqual(frame["executed_actions"], [])
                self.assertEqual(
                    frame["opening_pct"], episode["origin"]["opening_pct"]
                )
            self.assertEqual(
                hold["metrics"]["total_window_and_door_motion_pct"], 0.0
            )

    def test_independent_heuristic_never_opens_multiple_exterior_windows(self):
        for episode in self.artifact["episodes"]:
            windows = {
                e["id"] for e in episode["topology"]["openings"]
                if e["kind"] == "window"
            }
            for frame in episode["policies"]["Independent"]["frames"]:
                active = [
                    a for a in frame["executed_actions"]
                    if a["opening_id"] in windows and a["target_pct"] > 0
                ]
                self.assertLessEqual(len(active), 1)

    def test_training_and_test_seeds_do_not_overlap(self):
        self.assertFalse(
            set(self.artifact["training"]["train_seeds"])
            & set(self.artifact["evaluation"]["test_seeds"])
        )
        self.assertFalse(self.artifact["evaluation"]["structural_family_holdout"])
        self.assertEqual(
            self.artifact["status"], "EXPLORATORY_NOT_ENGINEERING_TRUTH"
        )

    def test_deterministic_artifact_checksum(self):
        again = same_origin_toy_ablation(
            train_count=4, test_count=2, horizon_steps=4, seed=80
        )
        self.assertEqual(
            self.artifact["artifact_sha256"], again["artifact_sha256"]
        )

    def test_tampered_origin_or_frames_fail_closed(self):
        broken = copy.deepcopy(self.artifact)
        broken["episodes"][0]["origin"]["co2_ppm"]["room1"] += 1
        with self.assertRaisesRegex(ValueError, "origin hash mismatch"):
            verify_toy_ablation(broken)

        broken = copy.deepcopy(self.artifact)
        broken["episodes"][0]["policies"]["BC"]["frames"].pop()
        with self.assertRaisesRegex(ValueError, "frame horizon"):
            verify_toy_ablation(broken)

    def test_false_structural_holdout_or_physical_claim_fails_closed(self):
        broken = copy.deepcopy(self.artifact)
        broken["evaluation"]["structural_family_holdout"] = True
        with self.assertRaisesRegex(ValueError, "boundary"):
            verify_toy_ablation(broken)

        broken = copy.deepcopy(self.artifact)
        broken["status"] = "PHYSICAL_VALIDATED"
        with self.assertRaisesRegex(ValueError, "physical truth"):
            verify_toy_ablation(broken)

    def test_missing_policy_fails_closed(self):
        broken = copy.deepcopy(self.artifact)
        del broken["episodes"][0]["policies"]["Offline-Q"]
        with self.assertRaisesRegex(ValueError, "policy coverage"):
            verify_toy_ablation(broken)

    def test_toy_structural_family_holdout_is_explicit(self):
        payload = same_origin_toy_ablation(
            train_count=4,
            test_count=3,
            horizon_steps=4,
            seed=90,
            test_families=("hub", "loop", "irregular"),
        )
        self.assertTrue(verify_toy_ablation(payload))
        self.assertTrue(payload["evaluation"]["structural_family_holdout"])
        self.assertEqual(
            {episode["topology_family"] for episode in payload["episodes"]},
            {"hub", "loop", "irregular"},
        )
        self.assertEqual(payload["training"]["train_topology_families"], ["chain"])
        # Interior door graph topology really differs, not just room IDs.
        edge_counts = [
            sum(edge["kind"] == "door" for edge in episode["topology"]["openings"])
            for episode in payload["episodes"]
        ]
        self.assertEqual(edge_counts, [4, 5, 5])
        hub = payload["episodes"][0]["topology"]
        degree = {
            zone["id"]: sum(
                edge["kind"] == "door"
                and zone["id"] in (edge["source"], edge["target"])
                for edge in hub["openings"]
            )
            for zone in hub["zones"]
        }
        self.assertEqual(max(degree.values()), 4)

    def test_unsupported_structural_family_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "test_families"):
            same_origin_toy_ablation(
                train_count=1, test_count=1, horizon_steps=1,
                test_families=("not-a-topology",),
            )

    def test_independent_policy_no_eligible_window(self):
        policy = IndependentWindowPolicy()
        obs = {
            "co2_ppm": {"room1": 800, "room2": 900},
            "opening_zone": {"W1": "room1", "W2": "room2"},
            "interior_openings": ["D1"],
            "rain": False,
        }
        result = {a.opening_id: a.target_pct for a in policy(obs)}
        self.assertEqual(result, {"W1": 0, "W2": 0, "D1": 100})


if __name__ == "__main__":
    unittest.main()
