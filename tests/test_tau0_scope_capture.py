import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location(
    "capture_physical_tau0_scope_test",
    ROOT/"examples"/"capture_physical_tau0.py",
)
module=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

SCOPE_A="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
SCOPE_B="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def preflight():
    base={key:None for key in module._CONTEXT_KEYS}
    base.update({
        "position_tolerance_pct":1.0,
        "commissioning_behavior_witness":{
            "acceptance_policy":{
                "requested_excursion_pct":5.0,
                "max_first_excursion_pct":5.0,
            },
        },
        "baseline_position_feedback":{
            "position_pct":0.0,
            "timestamp":1.0,
            "measured":True,
        },
    })
    return base


class Driver:
    def __init__(self):
        self.last_command_idempotency_scope_id=None


class Tau0ScopeCaptureTests(unittest.TestCase):
    def test_probe_closeout_scope_drift_fails_after_safe_closeout(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            out=root/"tau0.jsonl"
            receipt=root/"audit.json"
            driver=Driver()

            def fake_record(*args,**kwargs):
                driver.last_command_idempotency_scope_id=SCOPE_A
                out.write_text("{}\n",encoding="utf-8")
                return SimpleNamespace(
                    id="trajectory-1",
                    environment_kind="physical",
                    steps=[],
                )

            closeout_called={"value":False}
            def fake_closeout(*args,**kwargs):
                closeout_called["value"]=True
                driver.last_command_idempotency_scope_id=SCOPE_B
                return {
                    "confirmed_closed":True,
                    "feedback":{
                        "actuator_id":"W1",
                        "timestamp":12.0,
                        "measured_position_pct":0.0,
                        "quality":"encoder-measured",
                    },
                }

            with patch.object(
                module,
                "validate_physical_tau0_preconditions",
                return_value=preflight(),
            ), patch.object(
                module,
                "record_physical_trajectory",
                side_effect=fake_record,
            ), patch.object(
                module,
                "trajectory_last_feedback_timestamp",
                return_value=10.0,
            ), patch.object(
                module,
                "_safe_closeout",
                side_effect=fake_closeout,
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "idempotency scope drift",
                ):
                    module.capture_physical_tau0(
                        driver=driver,
                        opening_id="W1",
                        topology_id="test",
                        steps=1,
                        out=out,
                        receipt=receipt,
                        commission_bundle=root/"bringup.json",
                    )

            self.assertTrue(closeout_called["value"])
            self.assertFalse(receipt.exists())


if __name__=="__main__":
    unittest.main()
