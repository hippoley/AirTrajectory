# Three real-execution gates (P0)

The current green tests for PRs #223–#225 cover the launch gateway, an annotated scene fixture, symbolic CONTAM IR, and a non-rendering projection model. **None is a real native save/restart/reload, physical ContamX solve, or rendered 3D overlay.**

## 1. Native Persistence Gate
Run the pinned full Pascal app: `bash scripts/start-full-editor.sh`.
Use Playwright against `http://127.0.0.1:3002/` to create a two-room layout with window and door. Save the scene using **native Pascal persistence** and capture SceneNodes IDs/positions/openings. Restart the service with `docker compose -f compose.pascal-native.yml restart pascal-editor` (**not** `down -v`). Reopen the same project, export the native scene again, compare canonical node snapshots, and retain browser trace and compose restart logs. If either snapshot cannot be extracted via the native save/reload API, leave this gate BLOCKED.

## 2. CONTAM Execution Gate
Use the **same saved native scene** and its reviewed physical metadata to generate LayoutContract. The full PRJ toolchain is `compile_contam_ir`, `allocate_contam_ids`, `bind_airflow_elements`, `bind_boundary_profile`, `bind_prj_serialization_profile`, and `write_minimal_prj`. Do not silently repurpose the *illustrative* `examples/contam_prj_profile.example.json` as engineering-validated inputs. Run an approved model through `verify_engineering_contam_runtime` and archive the exact PRJ, subprocess/runtime evidence, solver outputs, hashes and version. Symbolic `READY_FOR_PRJ_WRITER` is not sufficient.

## 3. Native Rendering Gate
Feed the actual engineering runtime receipt to `examples/project_contam_to_pascal.py` and instrument upstream Pascal renderer by native node IDs. Capture the actual rendered canvas in BOTH 2D and 3D, plus a Playwright trace exercising the node-linked overlays. The projection JSON's `rendered_in_pascal=false` proves this gate is still pending until real DOM/canvas evidence exists.

## Independent evidence integrity check
Collect artifacts in an evidence folder containing `manifest.json`. Run:
```bash
python scripts/verify_pascal_three_gates.py evidence/manifest.json
```
The manifest uses `schema_version=1.0`, one lowercase 64-char `source_scene_sha256`, and exact gate keys `native_persistence`, `contam_execution`, `native_rendering`. Each gate needs `status=executed`, identical source scene hash, `runner`, `execution_command`, and an `artifacts` object whose entries each contain a path relative to the manifest folder and a SHA-256 digest. Mandatory artifact names are declared in `scripts/verify_pascal_three_gates.py`. Persistence also needs identical `node_state_before` and `node_state_after`; rendering needs exactly matching `rendered_node_ids`; solver needs `real_solver=true`, a version, `successful_solver_exit=true`, and `parsed_solver_results=true`.

The verifier checks manifest completeness, on-disk artifacts and internal consistency; **it cannot independently authenticate the execution host or certify the physical correctness of model parameters**. Validate CI identity, signed/provenance logs and independent replay before claiming external verification. There is intentionally no dummy PASS manifest.
