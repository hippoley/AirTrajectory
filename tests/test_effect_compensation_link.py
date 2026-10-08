from dataclasses import dataclass
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_replanned_physical_step_effect_identity",
    ROOT / "examples" / "run_replanned_physical_step.py",
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


@dataclass
class Feedback:
    measured_position_pct: float | None
    timestamp: float


class Driver:
    def __init__(self, feedback):
        self.feedback = feedback
        self.commands = []

    def set_position(self, opening_id, target_pct):
        self.commands.append((opening_id, target_pct))
        return self.feedback


def test_safe_closeout_is_distinct_linked_effect():
    driver = Driver(Feedback(measured_position_pct=0.0, timestamp=11.0))
    result = module._safe_closeout_after_sensor_failure(
        driver,
        "W1",
        Feedback(measured_position_pct=5.0, timestamp=10.0),
        compensates_effect_id="effect-original",
    )

    assert result["attempted"] is True
    assert result["confirmed_closed"] is True
    assert result["effect_class"] == "mutating"
    assert result["compensates_effect_id"] == "effect-original"
    assert len(result["compensation_effect_id"]) == 64
    assert result["compensation_effect_id"] != "effect-original"
    assert driver.commands == [("W1", 0.0)]


def test_no_closeout_needed_does_not_invent_compensation_effect():
    driver = Driver(Feedback(measured_position_pct=0.0, timestamp=11.0))
    result = module._safe_closeout_after_sensor_failure(
        driver,
        "W1",
        Feedback(measured_position_pct=0.0, timestamp=10.0),
        compensates_effect_id="effect-original",
    )

    assert result["attempted"] is False
    assert result["confirmed_closed"] is True
    assert result["compensation_effect_id"] is None
    assert driver.commands == []
