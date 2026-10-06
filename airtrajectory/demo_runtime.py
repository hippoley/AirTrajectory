"""Unified runtime snapshot for the multi-space / multi-window demo.

One resolved snapshot is the hand-off point for:
- browser/UI state,
- physics compiler inputs,
- trajectory provenance.

The current floor-plan geometry remains fixed, while opening positions/states
may change per topology revision.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from .agents import MultiWindowRuleAgent
from .environment import ToyMultizoneEnvironment
from .layout import LayoutContract
from .rollout import rollout


def _sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class DemoRuntimeSnapshot:
    layout: LayoutContract
    topology_revision: int
    opening_positions: dict[str, float]
    opening_states: dict[str, float]

    @classmethod
    def resolve(
        cls,
        layout: LayoutContract,
        *,
        topology_revision: int = 0,
        opening_positions: dict[str, float] | None = None,
        opening_states: dict[str, float] | None = None,
    ) -> "DemoRuntimeSnapshot":
        positions = {o.id: o.position_t for o in layout.openings}
        states = {o.id: o.initial_open_pct for o in layout.openings}
        valid = set(positions)

        for label, overrides in (
            ("position", opening_positions or {}),
            ("state", opening_states or {}),
        ):
            unknown = set(overrides) - valid
            if unknown:
                raise ValueError(
                    f"unknown opening {label} overrides: "
                    + ",".join(sorted(unknown))
                )

        for opening_id, value in (opening_positions or {}).items():
            numeric = float(value)
            if not 0 <= numeric <= 1:
                raise ValueError(
                    f"opening {opening_id} position must be between 0 and 1"
                )
            positions[opening_id] = numeric

        for opening_id, value in (opening_states or {}).items():
            numeric = float(value)
            if not 0 <= numeric <= 100:
                raise ValueError(
                    f"opening {opening_id} state must be between 0 and 100"
                )
            states[opening_id] = numeric

        return cls(
            layout=layout,
            topology_revision=int(topology_revision),
            opening_positions=positions,
            opening_states=states,
        )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "topology_id": self.layout.topology_id,
            "layout_contract_sha256": self.layout.sha256(),
            "topology_revision": self.topology_revision,
            "opening_positions": dict(sorted(self.opening_positions.items())),
            "opening_states": dict(sorted(self.opening_states.items())),
        }

    def sha256(self) -> str:
        return _sha256(self.canonical_payload())

    def trajectory_context(self) -> dict[str, Any]:
        return {
            **self.layout.trajectory_context(
                topology_revision=self.topology_revision,
                opening_positions=self.opening_positions,
            ),
            "opening_states": dict(self.opening_states),
            "demo_runtime_snapshot_sha256": self.sha256(),
        }

    def web_payload(self) -> dict[str, Any]:
        payload = self.layout.web_snapshot()
        opening_map = {o["id"]: o for o in payload["openings"]}
        for opening_id, position in self.opening_positions.items():
            opening_map[opening_id]["position_t"] = position
            opening_map[opening_id]["initial_open_pct"] = self.opening_states[
                opening_id
            ]
        payload["runtime"] = {
            "topology_revision": self.topology_revision,
            "snapshot_sha256": self.sha256(),
        }
        return payload

    def physics_input(self) -> dict[str, Any]:
        contract = self.layout.contam_compile_contract(
            opening_positions=self.opening_positions,
        )
        contract["topology_revision"] = self.topology_revision
        contract["opening_states"] = dict(self.opening_states)
        contract["demo_runtime_snapshot_sha256"] = self.sha256()
        return contract

    def toy_environment(
        self,
        *,
        initial_co2: dict[str, float] | None = None,
        outdoor_co2: float = 430.0,
        horizon_steps: int = 60,
    ) -> ToyMultizoneEnvironment:
        env = ToyMultizoneEnvironment(
            self.layout.to_building_topology(),
            initial_co2=initial_co2,
            outdoor_co2=outdoor_co2,
            horizon_steps=horizon_steps,
        )
        original_reset = env.reset

        def reset(seed=None):
            obs, info = original_reset(seed)
            env.openings.update(self.opening_states)
            obs = env._observation()
            info.update(
                {
                    "topology_revision": self.topology_revision,
                    "demo_runtime_snapshot_sha256": self.sha256(),
                }
            )
            return obs, info

        env.reset = reset
        return env

    def rollout_rule_policy(
        self,
        *,
        initial_co2: dict[str, float] | None = None,
        outdoor_co2: float = 430.0,
        max_steps: int = 30,
        safety_resolver=None,
    ):
        topology = self.layout.to_building_topology()
        env = self.toy_environment(
            initial_co2=initial_co2,
            outdoor_co2=outdoor_co2,
            horizon_steps=max_steps,
        )
        policy = MultiWindowRuleAgent(topology)
        return rollout(
            env,
            policy,
            topology_id=self.layout.topology_id,
            policy_id="multi-window-rule-v1",
            max_steps=max_steps,
            safety_resolver=safety_resolver,
            context_extra=self.trajectory_context(),
        )
