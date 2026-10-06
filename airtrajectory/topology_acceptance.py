"""Cross-topology acceptance checks for the shared runtime contract.

This module verifies that UI, physics compilation, trajectory provenance, and
policy actions are all derived from the supplied LayoutContract rather than
fixed demo identifiers.  It is intentionally backend-neutral: a topology can
pass this contract before an engineering CONTAM profile exists.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .demo_runtime import DemoRuntimeSnapshot
from .layout import LayoutContract
from .spatial_compile import compile_spatial_plan


def _sorted(values: Iterable[str]) -> list[str]:
    return sorted(str(value) for value in values)


def verify_topology_runtime(
    layout: LayoutContract,
    *,
    topology_revision: int = 1,
    max_steps: int = 1,
) -> dict[str, Any]:
    """Return a machine-readable portability receipt for one topology."""

    snapshot = DemoRuntimeSnapshot.resolve(
        layout,
        topology_revision=topology_revision,
    )
    web = snapshot.web_payload()
    physics = snapshot.physics_input()
    spatial = compile_spatial_plan(
        layout,
        opening_positions=snapshot.opening_positions,
    )
    trajectory_context = snapshot.trajectory_context()

    initial_co2 = {room.id: 1300.0 for room in layout.rooms}
    trajectory = snapshot.rollout_rule_policy(
        initial_co2=initial_co2,
        max_steps=max_steps,
    )

    expected_zone_ids = _sorted(room.id for room in layout.rooms)
    expected_opening_ids = _sorted(opening.id for opening in layout.openings)
    expected_action_ids = _sorted(
        opening.id for opening in layout.openings if opening.state_editable
    )

    web_zone_ids = _sorted(room["id"] for room in web["rooms"])
    web_opening_ids = _sorted(opening["id"] for opening in web["openings"])
    physics_zone_ids = _sorted(zone["id"] for zone in physics["zones"])
    physics_opening_ids = _sorted(
        opening["id"] for opening in physics["openings"]
    )
    spatial_zone_ids = _sorted(zone["id"] for zone in spatial["zones"])
    spatial_opening_ids = _sorted(
        opening["id"] for opening in spatial["openings"]
    )
    trajectory_opening_ids = _sorted(
        trajectory_context["opening_states"].keys()
    )

    action_ids = []
    if trajectory.steps:
        action_ids = _sorted(
            action.opening_id
            for action in trajectory.steps[0].executed_actions
        )

    snapshot_hash = snapshot.sha256()
    checks = {
        "web_zones_match": web_zone_ids == expected_zone_ids,
        "web_openings_match": web_opening_ids == expected_opening_ids,
        "physics_zones_match": physics_zone_ids == expected_zone_ids,
        "physics_openings_match": physics_opening_ids == expected_opening_ids,
        "spatial_zones_match": spatial_zone_ids == expected_zone_ids,
        "spatial_openings_match": spatial_opening_ids == expected_opening_ids,
        "trajectory_openings_match": (
            trajectory_opening_ids == expected_opening_ids
        ),
        "policy_actions_match": action_ids == expected_action_ids,
        "web_hash_matches": (
            web["runtime"]["snapshot_sha256"] == snapshot_hash
        ),
        "physics_hash_matches": (
            physics["demo_runtime_snapshot_sha256"] == snapshot_hash
        ),
        "trajectory_hash_matches": (
            trajectory.context["demo_runtime_snapshot_sha256"]
            == snapshot_hash
        ),
        "trajectory_topology_matches": (
            trajectory.context["topology_id"] == layout.topology_id
        ),
    }

    return {
        "schema_version": "0.1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "topology_id": layout.topology_id,
        "topology_revision": topology_revision,
        "layout_contract_sha256": layout.sha256(),
        "demo_runtime_snapshot_sha256": snapshot_hash,
        "expected": {
            "zone_ids": expected_zone_ids,
            "opening_ids": expected_opening_ids,
            "policy_action_ids": expected_action_ids,
        },
        "observed": {
            "web_zone_ids": web_zone_ids,
            "web_opening_ids": web_opening_ids,
            "physics_zone_ids": physics_zone_ids,
            "physics_opening_ids": physics_opening_ids,
            "spatial_zone_ids": spatial_zone_ids,
            "spatial_opening_ids": spatial_opening_ids,
            "trajectory_opening_ids": trajectory_opening_ids,
            "policy_action_ids": action_ids,
        },
        "checks": checks,
    }


def verify_topology_files(paths: Iterable[str | Path]) -> dict[str, Any]:
    """Verify two or more topology files through the same runtime code path."""

    layouts = [LayoutContract.from_file(path) for path in paths]
    if len(layouts) < 2:
        raise ValueError("cross-topology acceptance requires at least two layouts")

    topology_ids = [layout.topology_id for layout in layouts]
    if len(set(topology_ids)) != len(topology_ids):
        raise ValueError("cross-topology acceptance requires distinct topology_id values")

    receipts = [
        verify_topology_runtime(layout, topology_revision=index + 1)
        for index, layout in enumerate(layouts)
    ]
    opening_sets = {
        tuple(receipt["expected"]["opening_ids"]) for receipt in receipts
    }
    distinct_opening_vocabularies = len(opening_sets) == len(receipts)

    passed = (
        distinct_opening_vocabularies
        and all(receipt["status"] == "PASS" for receipt in receipts)
    )

    return {
        "schema_version": "0.1",
        "status": "PASS" if passed else "FAIL",
        "topology_count": len(receipts),
        "distinct_topology_ids": len(set(topology_ids)) == len(receipts),
        "distinct_opening_vocabularies": distinct_opening_vocabularies,
        "receipts": receipts,
    }
