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
from .contam import CONTAMEnvironment, ContamControl
from .multiwindow_physical import MultiWindowPhysicalEnvironment
from .physical import PhysicalWindowDriver, SafetyDecision, SafetyResolver
from .rollout import rollout



class TopologyAwareSafetyResolver:
    """Apply environmental safety rules to exterior openings only."""

    def __init__(self, topology, base_resolver):
        self.topology=topology
        self.base=base_resolver

    def resolve(self, observation, actions):
        proposed=list(actions)
        exterior_ids={
            edge.id
            for edge in self.topology.openings.values()
            if edge.source==self.topology.outside_id
            or edge.target==self.topology.outside_id
        }
        exterior=[a for a in proposed if a.opening_id in exterior_ids]
        decision=self.base.resolve(observation,exterior)
        executed_exterior={a.opening_id:a for a in decision.executed}
        executed=[
            executed_exterior.get(a.opening_id,a)
            if a.opening_id in exterior_ids else a
            for a in proposed
        ]
        return SafetyDecision(
            proposed=proposed,
            executed=executed,
            intervention=decision.intervention,
        )

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
    contam_prj_path=None,
    contam_provenance: dict | None = None,
    contam_binding_factory=None,
) -> DemoRunResult:
    topology = snapshot.layout.to_building_topology()
    policy = MultiWindowRuleAgent(topology)
    resolver = TopologyAwareSafetyResolver(
        topology,
        safety_resolver or SafetyResolver(),
    )

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


    if mode == "contam":
        if contam_prj_path is None or not isinstance(contam_provenance, dict):
            raise ValueError("contam mode requires PRJ path and provenance")

        zone_numbers = {
            key.split(":", 1)[1]: int(value)
            for key, value in contam_provenance["zone_numbers"].items()
            if key.startswith("zone:")
        }
        path_numbers = {
            key.split(":", 1)[1]: int(value)
            for key, value in contam_provenance["path_numbers"].items()
            if key.startswith("path:")
        }
        input_names = dict(contam_provenance.get("input_control_names") or {})
        opening_controls = {
            opening_id: ContamControl(control_name=name)
            for opening_id, name in input_names.items()
        }

        fixed = dict(fixed_openings or {})
        for opening_id in topology.openings:
            if opening_id not in opening_controls and opening_id not in fixed:
                fixed[opening_id] = snapshot.opening_states[opening_id]

        env = CONTAMEnvironment(
            topology,
            contam_prj_path,
            zone_numbers=zone_numbers,
            opening_controls=opening_controls,
            co2_contaminant_number=1,
            path_numbers=path_numbers,
            max_steps=max_steps,
            binding_factory=contam_binding_factory,
            fixed_openings=fixed,
            initial_openings=snapshot.opening_states,
        )
        try:
            trajectory = rollout(
                env,
                policy,
                topology_id=snapshot.layout.topology_id,
                policy_id="multi-window-rule-v1",
                max_steps=max_steps,
                safety_resolver=resolver,
                context_extra={
                    **snapshot.trajectory_context(),
                    "demo_backend_mode": "contam",
                    "contam_prj_path": str(contam_prj_path),
                    "contam_prj_sha256": contam_provenance.get("sha256"),
                    "contam_path_numbers": path_numbers,
                    "contam_zone_numbers": zone_numbers,
                    "contam_input_control_names": input_names,
                    "fixed_opening_ids": sorted(fixed),
                },
                environment_kind="contam",
            )
        finally:
            env.close()
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

    raise ValueError("mode must be simulation, contam, or physical")
