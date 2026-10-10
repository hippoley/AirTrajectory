# Full Pascal Editor integration: no parallel SVG UI

The production editor is **pascalorg/editor** pinned by `scripts/start-full-editor.sh`. It includes Scene, Build, Paint and Items tools, native canvas, material/furniture features and SQLite persistence. AirTrajectory should import native SceneGraphs through Pascal's own REST API instead of building another editor.

### Load a private residence into the real editor

```bash
bash scripts/start-full-editor.sh
node scripts/import-pascal-native-scene.cjs /private/path/residence-native.json --id private-residence-v1 --name "Residential Demo"
# Open http://localhost:3002/scene/private-residence-v1
```

The importer checks graph identity, rejects an existing scene ID without overwriting it, POSTs the complete SceneGraph to native `/api/scenes`, GETs the stored graph back and verifies node IDs and original geometry. It does not alter the input file. Run this only after a private CAD draft has passed the upstream scene-schema validation: graph import is **not** proof that 3D wall renderings, doors, window hosts, furniture or physics are correct.

**Private data boundary:** Never commit the homeowner CAD, resulting precise residential SceneGraph, or original house coordinates to a public repository. Run import against a trusted local Pascal instance. A physically reviewed sidecar lives outside the scene and binds to the source SHA-256.

### Real CI receipt

`.github/workflows/pascal-native-upstream-smoke.yml` now imports Pascal's full upstream two-bedroom template against the **live production editor's** native persistence API. It is separate from the existing save/restart/reopen check. A green result proves the import API path, not the incomplete private CAD reconstruction.

### Next missing gates

1. CAD double-line wall centreline and measured wall thickness; avoid importing 197 wall-chain sketches as actual 3D walls.
2. Native doors/windows only with confirmed wall host and dimensions.
3. Wall/material/furniture integration using the upstream tools, tested through real Playwright interactions.
4. Physical sidecar, real CONTAM PRJ on this same native scene, and native scene result overlays.
