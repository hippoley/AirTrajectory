"""Public decision API is thin, deterministic and never authorizes hardware."""
import json
from pathlib import Path
import unittest

from airtrajectory import evaluate, ObjectiveContract, CanonicalWorldState, EvidenceRef
from airtrajectory.objective import compile_user_goal

FIXTURE = Path(__file__).resolve().parents[1] / "examples/multi_environment_conflict_v0.2.json"


class PublicDecisionAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_public_api_matches_canonical_comparator(self):
        from airtrajectory.multi_environment_compare import compare_candidate_futures
        p = self.fixture
        objective = compile_user_goal(p["user_goal"])
        report = evaluate(
            candidates=p["candidates"],
            origin_openings=p["origin_opening_pct"],
            objective=objective,
        )
        self.assertEqual(
            report,
            compare_candidate_futures(
                p["candidates"], objective=objective,
                origin_openings=p["origin_opening_pct"],
            ),
        )
        self.assertFalse(report["execution_authorized"])
        self.assertEqual(report["recommended"], ["SHORT_CROSSFLOW"])

    def test_public_goal_entry_uses_same_contract(self):
        p = self.fixture
        report = evaluate(
            candidates=p["candidates"],
            origin_openings=p["origin_opening_pct"],
            user_goal=p["user_goal"],
        )
        self.assertEqual(report["recommended"], ["SHORT_CROSSFLOW"])

    def test_unknown_language_fails_closed(self):
        p = self.fixture
        with self.assertRaisesRegex(ValueError, "outside"):
            evaluate(
                candidates=p["candidates"],
                origin_openings=p["origin_opening_pct"],
                user_goal="Please invent the optimal energy plan.",
            )

    def test_ambiguous_or_missing_objective_fails_closed(self):
        p = self.fixture
        with self.assertRaisesRegex(ValueError, "exactly one"):
            evaluate(candidates=p["candidates"], origin_openings=p["origin_opening_pct"])
        with self.assertRaisesRegex(ValueError, "exactly one"):
            evaluate(
                candidates=p["candidates"], origin_openings=p["origin_opening_pct"],
                objective=compile_user_goal(p["user_goal"]), user_goal=p["user_goal"],
            )

    def test_public_world_state_does_not_grant_physical_authorization(self):
        self.assertTrue(callable(CanonicalWorldState.from_parts))
        self.assertRaises(ValueError, EvidenceRef, "E4", "sensor", "fake")


if __name__ == "__main__":
    unittest.main()
