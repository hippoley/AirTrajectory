"""H1a provenance-matched replay preparation.

Pure, dependency-free data selection. This does NOT claim trained-policy gains.
Records with missing physics lineage are excluded from both paired arms.
"""
from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
import json
import random
from typing import Any, Mapping, Sequence


PHYSICS_KEYS = (
    "backend", "backend_version", "time_step_s",
    "boundary_sha256", "actuation_schema_sha256",
)


def physics_fingerprint(row: Mapping[str, Any]) -> str:
    provenance = row.get("physics_provenance")
    if not isinstance(provenance, Mapping):
        raise ValueError("missing physics_provenance")
    missing = [key for key in PHYSICS_KEYS if provenance.get(key) in (None, "")]
    if missing:
        raise ValueError("missing physics provenance fields: " + ",".join(missing))
    payload = {key: provenance[key] for key in PHYSICS_KEYS}
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def prepare_paired_replay(
    rows: Sequence[Mapping[str, Any]],
    *,
    target_fingerprint: str,
    sample_size: int,
    seed: int,
    group_field: str = "trajectory_id",
) -> dict[str, Any]:
    """Create equal-size matched and mixed arms without trajectory-group leakage.

    A group belongs to a single arm. Mixed arm samples only non-target physics
    provenance, making this an informative strict provenance contrast rather
    than a randomized mixture of both groups.
    """
    if sample_size < 1:
        raise ValueError("sample_size must be positive")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("is_counterfactual"):
            continue  # Counterfactual transitions are not executed behavior.
        gid = row.get(group_field)
        if gid in (None, ""):
            raise ValueError("trajectory identity required for leakage-safe split")
        data = dict(row)
        data["_physics_fingerprint"] = physics_fingerprint(row)
        grouped[str(gid)].append(data)

    compatible, other = [], []
    for gid, group in sorted(grouped.items()):
        kinds = {row["_physics_fingerprint"] for row in group}
        if len(kinds) != 1:
            raise ValueError(f"mixed physics inside trajectory: {gid}")
        if target_fingerprint in kinds:
            compatible.append((gid, group))
        else:
            other.append((gid, group))

    rng = random.Random(seed)
    rng.shuffle(compatible)
    rng.shuffle(other)

    def collect(groups: list[tuple[str, list[dict[str, Any]]]]) -> list[dict[str, Any]]:
        selected, total = [], 0
        for gid, group in groups:
            if total + len(group) > sample_size:
                continue
            selected.extend(group)
            total += len(group)
            if total == sample_size:
                break
        if total != sample_size:
            raise ValueError(
                f"insufficient whole-trajectory rows for paired {sample_size} samples"
            )
        return selected

    matched = collect(compatible)
    mixed = collect(other)
    matched_ids = {str(r[group_field]) for r in matched}
    mixed_ids = {str(r[group_field]) for r in mixed}
    if matched_ids & mixed_ids:
        raise RuntimeError("trajectory group leakage across arms")
    return {
        "contract": "physics-matched-replay-h1a-v0.1",
        "seed": seed,
        "target_fingerprint": target_fingerprint,
        "samples_per_arm": sample_size,
        "matched": matched,
        "mixed": mixed,
        "metrics": {
            "matched_trajectories": len(matched_ids),
            "mixed_trajectories": len(mixed_ids),
            "leakage_groups": 0,
        },
        "claim_boundary": (
            "This is a dataset-provenance contrast, not evidence of training or "
            "out-of-distribution improvement; match arm sizes, policy capacity "
            "and evaluation conditions before causal claims."
        ),
    }
