from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
import uuid


@dataclass(frozen=True)
class TransitionAction:
    opening_id: str
    target_pct: float

    def __post_init__(self):
        if not 0 <= self.target_pct <= 100:
            raise ValueError("target_pct must be in [0, 100]")


@dataclass
class RewardVector:
    iaq: float = 0.0
    comfort: float = 0.0
    energy: float = 0.0
    safety: float = 0.0
    actuator_wear: float = 0.0
    override: float = 0.0

    def scalar(self, weights: Optional[Dict[str, float]] = None) -> float:
        weights = weights or {
            "iaq": 1.0,
            "comfort": 0.5,
            "energy": 0.2,
            "safety": 4.0,
            "actuator_wear": 0.1,
            "override": 0.5,
        }
        return sum(getattr(self, key) * value for key, value in weights.items())


@dataclass
class TrajectoryStep:
    index: int
    observation: Dict[str, Any]
    proposed_actions: List[TransitionAction]
    executed_actions: List[TransitionAction]
    next_observation: Dict[str, Any]
    reward: RewardVector
    intervention: Optional[str] = None
    terminated: bool = False
    info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Trajectory:
    topology_id: str
    policy_id: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    context: Dict[str, Any] = field(default_factory=dict)
    steps: List[TrajectoryStep] = field(default_factory=list)

    @property
    def return_value(self) -> float:
        return sum(step.reward.scalar() for step in self.steps)

    def append(self, step: TrajectoryStep) -> None:
        if step.index != len(self.steps):
            raise ValueError("trajectory step indices must be contiguous")
        self.steps.append(step)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["return"] = self.return_value
        return payload


class TrajectoryStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, trajectory: Trajectory) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(trajectory.to_dict(), ensure_ascii=False) + "\n")
