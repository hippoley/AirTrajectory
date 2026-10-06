"""Unified orchestration for the multi-space / multi-window demo.

A single DemoRuntimeSnapshot and policy drive either:
- the simulation backend, or
- a fail-closed multi-window physical backend.

Both modes emit the same Trajectory schema and embed the same runtime snapshot
provenance. Backend differences are represented as evidence, not orchestration.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .agents import MultiWindowRuleAgent
from .demo_runtime import DemoRuntimeSnapshot
from .multiwindow_physical import MultiWindowPhysicalEnvironment
from .physical import PhysicalWindowDriver, SafetyResolver
from .rollout import rollout


@dataclass(frozen=True)
class DemoRunResult:
    mode: str
    snapshot_sha256: str
    trajectory: object


def run_demo(
    snapshot: DemoRuntimeSnapshot,
    *,
    mode: str,
    max_steps: int = 10,
    initial_co2: dict[str, float] | None = None,
    outdoor_co2: float = 430.0,
    drivers: Mapping[str, PhysicalWindowDriver] | None = None,
    fixed_openings: Mapping[str, float] | None = None,
    safety_resolver=None,
) -> DemoRunResult:
    topology = snapshot.layout.to_building_topology()
    policy = MultiWindowRuleAgent(topology)
    resolver = safety_resolver or SafetyResolver()

    if mode == "simulation":
        env = snapshot.toy_environment(
            initial_co2=initial_co2,
            outdoor_co2=outdoor_co2,
            horizon_steps=max_steps,
        )
        trajectory = rollout(
            env,
            policy,
            topology_id=snapshot.layout.topology_id,
            policy_id="multi-window-rule-v1",
            max_steps=max_steps,
            safety_resolver=resolver,
            context_extra={
                **snapshot.trajectory_context(),
                "demo_backend_mode": "simulation",
            },
            environment_kind="simulation",
        )
        return DemoRunResult(mode, snapshot.sha256(), trajectory)

    if mode == "physical":
        if not drivers:
            raise ValueError("physical mode requires per-opening drivers")

        exterior_controllable = {
            edge.id
            for edge in topology.openings.values()
            if edge.controllable
            and (
                edge.source == topology.outside_id
                or edge.target == topology.outside_id
            )
        }
        missing = exterior_controllable - set(drivers)
        if missing:
            raise ValueError(
                "physical mode missing drivers for exterior controllable openings: "
                + ",".join(sorted(missing))
            )

        fixed = dict(fixed_openings or {})
        for edge in topology.openings.values():
            if edge.id not in drivers and edge.id not in fixed:
                fixed[edge.id] = snapshot.opening_states[edge.id]

        env = MultiWindowPhysicalEnvironment(
            topology,
            drivers,
            fixed_openings=fixed,
            initial_openings=snapshot.opening_states,
            require_write_ready=True,
        )
        trajectory = rollout(
            env,
            policy,
            topology_id=snapshot.layout.topology_id,
            policy_id="multi-window-rule-v1",
            max_steps=max_steps,
            safety_resolver=resolver,
            context_extra={
                **snapshot.trajectory_context(),
                "demo_backend_mode": "physical",
                "physical_opening_ids": sorted(drivers),
                "fixed_opening_ids": sorted(fixed),
            },
            environment_kind="physical",
        )
        return DemoRunResult(mode, snapshot.sha256(), trajectory)

    raise ValueError("mode must be simulation or physical")
