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
