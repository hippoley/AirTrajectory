import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from airtrajectory.physical_origin_lease import (
    claim_physical_origin_execution,
    finalize_physical_origin_execution,
    recover_abandoned_physical_origin_execution,
    verify_physical_origin_execution_lease,
)


class PhysicalOriginLeaseTests(unittest.TestCase):
    def test_claim_is_atomic_and_same_origin_cannot_be_claimed_twice(self):
        with tempfile.TemporaryDirectory() as d:
            first=claim_physical_origin_execution(
                lease_dir=d,
                origin_receipt_sha256="a"*64,
                origin_sha256="b"*64,
                planner_receipt_sha256="c"*64,
                planner_step_sha256="d"*64,
                opening_id="W1",
                zone_id="living",
                claimed_at=10.0,
            )
            self.assertEqual(first["status"],"IN_FLIGHT")
            self.assertTrue(Path(first["lease_path"]).exists())
            with self.assertRaisesRegex(RuntimeError,"already been claimed"):
                claim_physical_origin_execution(
                    lease_dir=d,
                    origin_receipt_sha256="a"*64,
                    origin_sha256="b"*64,
                    planner_receipt_sha256="c"*64,
                    planner_step_sha256="d"*64,
                    opening_id="W1",
                    zone_id="living",
                    claimed_at=11.0,
                )

    def test_successful_claim_advances_and_stays_single_use(self):
        with tempfile.TemporaryDirectory() as d:
            claim=claim_physical_origin_execution(
                lease_dir=d,
                origin_receipt_sha256="a"*64,
                origin_sha256="b"*64,
                planner_receipt_sha256="c"*64,
                planner_step_sha256="d"*64,
                opening_id="W1",
                zone_id="living",
                claimed_at=10.0,
            )
            final=finalize_physical_origin_execution(
                lease_path=claim["lease_path"],
                status="ADVANCED",
                finalized_at=11.0,
                next_origin_receipt_sha256="e"*64,
                step_summary_sha256="f"*64,
            )
            self.assertEqual(final["status"],"ADVANCED")
            verified=verify_physical_origin_execution_lease(
                lease_path=claim["lease_path"],
                expected_origin_receipt_sha256="a"*64,
            )
            self.assertEqual(
                verified["next_physical_origin_receipt_sha256"],
                "e"*64,
            )
            with self.assertRaisesRegex(RuntimeError,"already been claimed"):
                claim_physical_origin_execution(
                    lease_dir=d,
                    origin_receipt_sha256="a"*64,
                    origin_sha256="b"*64,
                    planner_receipt_sha256="c"*64,
                    planner_step_sha256="d"*64,
                    opening_id="W1",
                    zone_id="living",
                    claimed_at=12.0,
                )

    def test_failed_claim_requires_recovery_and_never_reopens_origin(self):
        with tempfile.TemporaryDirectory() as d:
            claim=claim_physical_origin_execution(
                lease_dir=d,
                origin_receipt_sha256="a"*64,
                origin_sha256="b"*64,
                planner_receipt_sha256="c"*64,
                planner_step_sha256="d"*64,
                opening_id="W1",
                zone_id="living",
                claimed_at=10.0,
            )
            final=finalize_physical_origin_execution(
                lease_path=claim["lease_path"],
                status="RECOVERY_REQUIRED",
                finalized_at=11.0,
                recovery={
                    "error":"sensor timeout",
                    "requires_new_physical_origin":True,
                },
            )
            self.assertEqual(final["status"],"RECOVERY_REQUIRED")
            self.assertTrue(final["recovery"]["requires_new_physical_origin"])
            with self.assertRaisesRegex(RuntimeError,"already been claimed"):
                claim_physical_origin_execution(
                    lease_dir=d,
                    origin_receipt_sha256="a"*64,
                    origin_sha256="b"*64,
                    planner_receipt_sha256="c"*64,
                    planner_step_sha256="d"*64,
                    opening_id="W1",
                    zone_id="living",
                    claimed_at=12.0,
                )

    def test_live_owner_inflight_lease_cannot_be_recovered(self):
        with tempfile.TemporaryDirectory() as d:
            claim=claim_physical_origin_execution(
                lease_dir=d,
                origin_receipt_sha256="a"*64,
                origin_sha256="b"*64,
                planner_receipt_sha256="c"*64,
                planner_step_sha256="d"*64,
                opening_id="W1",
                zone_id="living",
                claimed_at=10.0,
                owner_host="host-a",
                owner_pid=1234,
            )
            with self.assertRaisesRegex(RuntimeError,"owner process is still running"):
                recover_abandoned_physical_origin_execution(
                    lease_path=claim["lease_path"],
                    recovered_at=20.0,
                    recovery_host="host-a",
                    process_alive_fn=lambda pid: True,
                )
            current=verify_physical_origin_execution_lease(
                lease_path=claim["lease_path"],
            )
            self.assertEqual(current["status"],"IN_FLIGHT")

    def test_dead_same_host_owner_is_sealed_as_recovery_required(self):
        with tempfile.TemporaryDirectory() as d:
            claim=claim_physical_origin_execution(
                lease_dir=d,
                origin_receipt_sha256="a"*64,
                origin_sha256="b"*64,
                planner_receipt_sha256="c"*64,
                planner_step_sha256="d"*64,
                opening_id="W1",
                zone_id="living",
                claimed_at=10.0,
                owner_host="host-a",
                owner_pid=1234,
            )
            recovered=recover_abandoned_physical_origin_execution(
                lease_path=claim["lease_path"],
                recovered_at=20.0,
                recovery_host="host-a",
                process_alive_fn=lambda pid: False,
            )
            self.assertEqual(recovered["status"],"RECOVERY_REQUIRED")
            self.assertTrue(recovered["recovery"]["requires_new_physical_origin"])
            self.assertEqual(
                recovered["recovery"]["reason"],
                "OWNER_PROCESS_NOT_RUNNING",
            )
            with self.assertRaisesRegex(RuntimeError,"already been claimed"):
                claim_physical_origin_execution(
                    lease_dir=d,
                    origin_receipt_sha256="a"*64,
                    origin_sha256="b"*64,
                    planner_receipt_sha256="c"*64,
                    planner_step_sha256="d"*64,
                    opening_id="W1",
                    zone_id="living",
                    claimed_at=21.0,
                )

    def test_cross_host_owner_cannot_be_declared_dead_locally(self):
        with tempfile.TemporaryDirectory() as d:
            claim=claim_physical_origin_execution(
                lease_dir=d,
                origin_receipt_sha256="a"*64,
                origin_sha256="b"*64,
                planner_receipt_sha256="c"*64,
                planner_step_sha256="d"*64,
                opening_id="W1",
                zone_id="living",
                claimed_at=10.0,
                owner_host="host-a",
                owner_pid=1234,
            )
            with self.assertRaisesRegex(RuntimeError,"across hosts"):
                recover_abandoned_physical_origin_execution(
                    lease_path=claim["lease_path"],
                    recovered_at=20.0,
                    recovery_host="host-b",
                    process_alive_fn=lambda pid: False,
                )
            current=verify_physical_origin_execution_lease(
                lease_path=claim["lease_path"],
            )
            self.assertEqual(current["status"],"IN_FLIGHT")

    def test_tampered_lease_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            claim=claim_physical_origin_execution(
                lease_dir=d,
                origin_receipt_sha256="a"*64,
                origin_sha256="b"*64,
                planner_receipt_sha256="c"*64,
                planner_step_sha256="d"*64,
                opening_id="W1",
                zone_id="living",
                claimed_at=10.0,
            )
            path=Path(claim["lease_path"])
            payload=json.loads(path.read_text(encoding="utf-8"))
            payload["opening_id"]="W9"
            path.write_text(json.dumps(payload),encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError,"lease SHA-256 mismatch"):
                verify_physical_origin_execution_lease(
                    lease_path=path,
                    expected_origin_receipt_sha256="a"*64,
                )

    def test_registry_directory_does_not_evict_old_origin(self):
        with tempfile.TemporaryDirectory() as d:
            for index in range(3):
                claim_physical_origin_execution(
                    lease_dir=d,
                    origin_receipt_sha256=(hex(index+10)[2:]*64)[:64],
                    origin_sha256="b"*64,
                    planner_receipt_sha256="c"*64,
                    planner_step_sha256="d"*64,
                    opening_id="W1",
                    zone_id="living",
                    claimed_at=10.0+index,
                )
            self.assertEqual(len(list(Path(d).glob("*.json"))),3)


if __name__=="__main__":
    unittest.main()
