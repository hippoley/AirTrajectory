# Pascal native residential default + Physical Metadata Sidecar

## Architectural default
Use the **real upstream Pascal `two-bedroom` SceneGraph** as the initial residential demonstration, not the old two-wall symbolic fixture. It contains an 80 m² apartment footprint (10 m × 8 m), 4 room zones, 9 walls, 4 doors and 5 windows with parent/child relationships. This is the **real native preset used by the CI**, not yet a custom interior styling package or a change to Pascal's initial homepage. Refine visual styling with original Pascal materials, 3D assets and furniture once the native preview is reviewed; preserve physical geometry and node IDs during styling.

Upstream file: `pascalorg/editor/packages/mcp/src/templates/two-bedroom.ts` at pinned commit `7fc874faec800e18f8be2dab78e7dc2ff2327bd7`.

## Physical binding
Never write analytical assumptions back to Pascal's native scene. Keep `scene.json` immutable and place physical declarations in a **separate** `physical-sidecar.json` with:
- `schema_version: "1.0"`, `topology_id` and `source_scene_sha256` (SHA-256 over exact source file bytes)
- `evidence_level`: `illustrative` or `engineering-reviewed`
- When reviewed: `review.reviewer_id`, `review.reviewed_at`, `review.evidence_reference`
- `nodes`: keyed by original Pascal node ID. Zone entries can carry `spaceRole:"room"`, `height_m`, `volume_m3`; walls `source_room`, `target_room`; windows/doors `sill_height_m` and `position_t` (the latter only when a native position is absent or consistent)

Command:

```sh
node scripts/bind-pascal-physical-sidecar.cjs scene.json physical-sidecar.json layout.json
python examples/compile_contam_ir.py layout.json --out symbolic-contam-ir.json
```

The binder rejects a mismatched source digest, missing node ID, conflicting native data, invalid fields or unreviewed attestation. LayoutContract conversion validates geometry and topology. Even a marked reviewed sidecar only produces `SIDECAR_BOUND_NOT_ENGINEERING_AUTHORIZED`; **it does not authorize a CONTAM engineering solve** without approved flow elements, boundary/weather, serialization profile, solver runtime and independent validation.

The native apartment is **not** automatically ready for the current LayoutContract: upstream zones lack AirTrajectory's engineering metadata, and many walls lack approved adjacency. The physical readiness auditor enumerates these missing fields. Confirm all node-level declarations before binding and do not invent them from visual proximity.

## Follow-on gates
1. Attach the sidecar to the persisted native scene bytes from the same GitHub CI run; assert the SHA matches.
2. Engineer review and sign off exact model inputs, including true adjacency and opening elevations.
3. Bind PRJ serialization profile to this model's native IDs, run real ContamX on Windows, archive solver outputs.
4. Project results back to same IDs and render in actual Pascal viewer with independent Playwright screenshots.
