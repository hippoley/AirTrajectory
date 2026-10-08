"""IdempotencyBench-native regression for stale readback after commit.

Copy this file into the root of gssanjana4/idempotencybench and run:

    python3 test_stale_readback_regression.py

It uses only the benchmark's existing public modules and stdlib.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from world import World, ToolTimeout, ToolServerError
from tasks import generate_tasks
from agents import AGENTS, run_episode


def make_task():
    return generate_tasks(per_domain=1)[0]


class StaleOnceReadbackWorld(World):
    """Hide the just-committed effect from exactly one post-failure readback."""

    def __init__(self, mitigation="none", failure_mode="timeout_after_commit"):
        super().__init__(mitigation=mitigation, failure_mode=failure_mode)
        self._hide_next_readback = False

    def call(self, tool, args, key, task_id):
        try:
            return super().call(tool, args, key, task_id)
        except (ToolTimeout, ToolServerError):
            if self.failure_mode in ("timeout_after_commit", "error_500_after_commit"):
                self._hide_next_readback = True
            raise

    def _list_effects(self, task_id):
        if self._hide_next_readback:
            self._hide_next_readback = False
            return "(no effects recorded)"
        return super()._list_effects(task_id)


class TestStaleReadbackAfterCommit(unittest.TestCase):
    def _run(self, agent_name, mitigation):
        task = make_task()
        world = StaleOnceReadbackWorld(
            mitigation=mitigation,
            failure_mode="timeout_after_commit",
        )
        run_episode(AGENTS[agent_name], world, task, "agent_retry")
        return world.ledger.violations(task.task_id), world.ledger.achieved(task.task_id, task.goal)

    def test_careful_agent_duplicates_when_readback_is_stale(self):
        violations, achieved = self._run("careful", "none")
        self.assertEqual(violations, 1)
        self.assertTrue(achieved)

    def test_runtime_receipt_still_prevents_duplicate(self):
        violations, achieved = self._run("careful", "runtime_receipts")
        self.assertEqual(violations, 0)
        self.assertTrue(achieved)

    def test_stable_key_plus_idempotency_key_still_prevents_duplicate(self):
        violations, achieved = self._run("stable_key", "idem_keys")
        self.assertEqual(violations, 0)
        self.assertTrue(achieved)


if __name__ == "__main__":
    unittest.main(verbosity=2)
