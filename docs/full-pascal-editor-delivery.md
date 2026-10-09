# Native full editor frontend — delivery entrypoint

**Use this frontend when the requirement is the complete Pascal building editor**, not a cosmetic clone of the SVG Spatial Studio.

## Start the complete app

Prerequisites: Docker Engine / Compose v2, Git, sufficient memory/disk space.

```bash
bash scripts/start-full-editor.sh
# Opens at http://localhost:3002 (override PASCAL_EDITOR_PORT if needed).
```

`scripts/start-full-editor.sh` checks out an exact, immutable public upstream Pascal release commit `7fc874faec800e18f8be2dab78e7dc2ff2327bd7` into ignored `.upstream/pascal-editor/`, verifies the MIT license, then builds and launches the upstream application's **own production Dockerfile**. The Docker service exposes the native application's complete Scene / Build / Paint / Items tooling, 2D/3D drawing/rendering, native viewer controls, and saves scenes in a Docker-managed `pascal-scenes` volume.

This route keeps the original Pascal application's bundled JS/CSS/assets together, instead of attempting to re-create those interactions in AirTrajectory's `web/studio.html`.

Inspect status / stop:
```bash
docker compose -f compose.pascal-native.yml ps
docker compose -f compose.pascal-native.yml logs --tail=100
docker compose -f compose.pascal-native.yml down
```

**Do not run `down -v` unless intending to erase saved scenes.**

## What is not yet done

- This is a full **self-hosted Pascal app**, not a static GitHub Pages deployment. `https://hippoley.github.io/AirTrajectory/studio.html` remains the simpler AirTrajectory editor, and cannot be represented as Pascal-native 1:1.
- The released open-source version is not guaranteed to be visually identical to Pascal's separate hosted **Pascal Next** preview, which upstream explicitly says is not in the open-source release.
- Native Pascal room/wall/window edits are not automatically valid AirTrajectory control instructions. `integrations/pascal-studio/pascal-scene-bridge.cjs` currently accepts **only** reviewed, annotated rectangular rooms; it rejects missing adjacency evidence, requires real volumes and normalized wall positions, and marks CONTAM compilation reserved.
- Native room editing/2D→3D should be verified in a graphical browser against the deployed container. Existing upstream compile CI does not constitute a visual 1:1 regression receipt.

## Ownership and upstream licensing

Upstream: https://github.com/pascalorg/editor — MIT; original author credit and license remain in the native checkout and runtime distribution. You may customize AirTrajectory's surrounding workflow and branding, but never remove required third-party notices.

**Acceptance sequence:** open native editor → draw four walls into a closed room → switch to 3D → place a door and window → save/reopen scene → export actual SceneNodes → add/review geometric and adjacency evidence → run `node scripts/export-pascal-scene.cjs input.json output.json` → pass Python LayoutContract readiness. The last three steps remain integration work, not yet verified.
