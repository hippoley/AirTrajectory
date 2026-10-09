# AirTrajectory × Pascal — native editor integration

## 1:1 building editor: use the real upstream source

For **authentic wall drawing, room editing, openings, plan/3D switching and scene tools**, run the actual open-source Pascal application, not the reduced AirTrajectory SVG Studio:

```bash
bash scripts/run-pascal-native.sh
```

This clones `pascalorg/editor` into ignored `.upstream/pascal-editor`, checks out **7fc874faec800e18f8be2dab78e7dc2ff2327bd7**, installs the locked Bun workspace, then starts the native `apps/editor` application. Requirements: Git and Bun 1.3.14. The upstream application determines the localhost address. This is the original editor's 2D/3D experience, not a screenshot or stylistic imitation.

Source/license: https://github.com/pascalorg/editor — **MIT, copyright (c) 2026 Pascal Group Inc.** Retain required MIT notices in distributions.

## Separate embedding experiment

`integrations/pascal-studio/app/page.tsx` uses the real published `@pascal-app/editor` React component but does **not** yet reproduce Pascal's complete native Build/Paint/Scene tool palette, persistence or bootstrap. Do not confuse this minimalist experimental host with the native application above.

## What is and isn't connected

- **Available from upstream Pascal:** genuine wall/room construction UX, 2D drawing and 3D scene/viewer capabilities. Run the native app to use them.
- **Available from AirTrajectory:** editable JSON LayoutContract, door/window relationships, topology/path exploration and downstream physics interfaces at `web/studio.html`.
- **Not yet bridged:** Pascal's scene graph ↔ canonical `LayoutContract`, reliable physical room adjacency, building elevations/metric frames, and tested native solver compilation from a Pascal-produced scene. The real native editor launch does not imply these exist.
- **Verification:** `.github/workflows/pascal-native-upstream-smoke.yml` pins the exact upstream source and checks the native app's types after lockfile installation. This is different from a browser test of every upstream tool.
- A 1:1 **visual/product experience** is provided by the upstream app itself; extending it with AirTrajectory requires an explicit adapter and must not silently invent physical geometry or airflow values.

## Next acceptance gate

Export a native Pascal scene; parse typed building/level/room/wall/door/window nodes, preserve stable native IDs and units; require human correction of incomplete adjacency; produce `LayoutContract`; round-trip a second edited scene; run `verify_topology_runtime`. Keep the existing Studio as the stable browser-delivered fallback until these checks pass.

## Pascal scene export to canonical LayoutContract (new)

The optional React host now has a **导出原生场景 JSON** action, exporting the real `useScene.getState().nodes` object. Convert with:

```bash
node scripts/export-pascal-scene.cjs pascal-native-scene.json artifacts/pascal-layout.json
python examples/compile_contam_ir.py artifacts/pascal-layout.json
```

The second command is expected to **refuse** layouts without engineering-ready geometry; never interpret a successful JSON export as ContamX authorization.

This v0.1 adapter intentionally requires explicit, reviewed metadata on native Pascal nodes:

- `zone`: `spaceRole: "room"`, rectangular `polygon`, metadata `airtrajectory_height_m` and `airtrajectory_volume_m3`
- `wall`: Pascal `start`/`end` metre coordinates; metadata `airtrajectory_source_room` (zone ID), `airtrajectory_target_room` (zone ID or `OUTSIDE`)
- `window`/`door`: valid native `wallId`, physical `width`/`height`, metadata `airtrajectory_position_t` in [0,1]

Any missing measurements or adjacency cause an explicit BLOCKED error. The scene is hashed with SHA-256 and its original bytes form the provenance source. `tests/fixtures/pascal-scene-two-rooms.json` is a typed shape test with **supplied evidence metadata**, not a statement that arbitrary native Pascal saves already have those annotations.

The adapter is imported in `test.yml`, which confirms its output is accepted by Python's real `LayoutContract.from_file` parser. Arbitrary polygon handling, automatic review annotations, verified units in all Pascal versions, and true Pascal round trip are not closed.
