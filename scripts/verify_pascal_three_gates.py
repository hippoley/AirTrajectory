"""Strict three-gate evidence checker for real Pascal/CONTAM/3D executions.

Reads local evidence only. A valid manifest checks internal consistency, not whether
the producer ran the alleged software: independent CI and provenance are still required.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path


GATES = ("native_persistence", "contam_execution", "native_rendering")
REQUIRED = {
    "native_persistence": ("scene_before", "scene_after", "browser_trace", "restart_log"),
    "contam_execution": ("scene_export", "layout_contract", "prj", "solver_output", "runtime_receipt"),
    "native_rendering": ("projection", "screenshot_2d", "screenshot_3d", "browser_trace"),
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_manifest(manifest_path: Path) -> dict:
    manifest_path = manifest_path.resolve()
    root = manifest_path.parent
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if data.get("schema_version") != "1.0":
        raise ValueError("unsupported evidence manifest")
    scene_sha = data.get("source_scene_sha256")
    if not isinstance(scene_sha, str) or len(scene_sha) != 64 or any(c not in "0123456789abcdef" for c in scene_sha):
        raise ValueError("source_scene_sha256 must be lowercase sha256")
    gates = data.get("gates")
    if not isinstance(gates, dict) or set(gates) != set(GATES):
        raise ValueError("three named gates required")
    verified = {}
    for gate in GATES:
        record = gates[gate]
        if record.get("status") != "executed":
            raise ValueError(f"{gate} is not executed")
        if record.get("source_scene_sha256") != scene_sha:
            raise ValueError(f"{gate} scene hash drift")
        if not record.get("execution_command") or not record.get("runner"):
            raise ValueError(f"{gate} missing runner/command evidence")
        artifacts = record.get("artifacts")
        if not isinstance(artifacts, dict) or not set(REQUIRED[gate]).issubset(artifacts):
            raise ValueError(f"{gate} missing mandatory artifacts")
        verified[gate] = {}
        for name, metadata in artifacts.items():
            relpath = metadata.get("path") if isinstance(metadata, dict) else None
            expected = metadata.get("sha256") if isinstance(metadata, dict) else None
            if not isinstance(relpath, str) or not relpath or not isinstance(expected, str):
                raise ValueError(f"{gate}/{name} invalid artifact metadata")
            path = (root / relpath).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                raise ValueError(f"{gate}/{name} missing or unsafe artifact")
            if _sha(path) != expected:
                raise ValueError(f"{gate}/{name} SHA-256 mismatch")
            verified[gate][name] = expected
    persistence = gates["native_persistence"]
    node_before = persistence.get("node_state_before")
    node_after = persistence.get("node_state_after")
    if not isinstance(node_before, dict) or not node_before or node_before != node_after:
        raise ValueError("native save/reopen node state mismatch or absent")
    if set(gates["native_rendering"].get("rendered_node_ids", [])) != set(node_before):
        raise ValueError("3D rendered node IDs do not match persisted scene")
    solver = gates["contam_execution"]
    if not solver.get("real_solver") or not solver.get("solver_version"):
        raise ValueError("real solver/version claim missing")
    if not solver.get("successful_solver_exit") or not solver.get("parsed_solver_results"):
        raise ValueError("real solver result evidence missing")
    return {"status": "EVIDENCE_MANIFEST_INTEGRITY_VERIFIED", "source_scene_sha256": scene_sha,
            "gate_artifact_hashes": verified,
            "limitation": "Artifact and claim consistency only; independently validate execution provenance."}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        result = verify_manifest(args.manifest)
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
