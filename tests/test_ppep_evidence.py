import json
from pathlib import Path
import unittest

from airtrajectory.ppep import build_evidence, compute_evidence_hash, seal_evidence, validate_evidence

ROOT = Path(__file__).resolve().parents[1]

class PPEPEvidenceTests(unittest.TestCase):
    def sample(self, **overrides):
        kwargs = dict(
            probe_id="stale-readback",
            hypothesis="Stale matching readback must remain unverified",
            variant="stale",
            assignment_id="assignment-001",
            actor_id="pseudonymous-001",
            action="run_probe",
            timestamp="2026-10-08T09:00:00Z",
            prompted=False,
            previous_state={"position_pct": 10},
            result_state={"position_pct": 40, "fresh": False},
            outcome_type="real_world_action",
            verified=False,
            evidence_refs=[],
        )
        kwargs.update(overrides)
        return build_evidence(**kwargs)

    def test_unverified_false_is_valid_without_reality_evidence(self):
        record = self.sample()
        self.assertFalse(record["outcome"]["verified"])
        self.assertEqual(record["outcome"]["evidence_refs"], [])
        validate_evidence(record)

    def test_verified_true_requires_evidence_reference(self):
        with self.assertRaisesRegex(ValueError, "requires at least one"):
            self.sample(verified=True, evidence_refs=[])

    def test_verified_true_is_valid_with_evidence_reference(self):
        record = self.sample(
            verified=True,
            evidence_refs=["sensor://window/W1/readback/42"],
        )
        validate_evidence(record)

    def test_tampering_breaks_evidence_hash(self):
        record = self.sample()
        record["experiment"]["variant"] = "editable"
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            validate_evidence(record)

    def test_state_hashes_change_when_result_changes(self):
        first = self.sample(result_state={"position_pct": 40, "fresh": False})
        second = self.sample(result_state={"position_pct": 40, "fresh": True})
        self.assertNotEqual(
            first["interaction"]["result_state_hash"],
            second["interaction"]["result_state_hash"],
        )

    def test_examples_validate_or_fail_as_declared(self):
        valid = json.loads((ROOT / "ppep/examples/valid-unverified.json").read_text())
        validate_evidence(valid)
        invalid = json.loads((ROOT / "ppep/examples/invalid-verified-without-evidence.json").read_text())
        with self.assertRaises(ValueError):
            seal_evidence(invalid)

if __name__ == "__main__":
    unittest.main()
