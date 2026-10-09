# Pascal Editor integration (experimental)

This is an isolated Next.js host for upstream `@pascal-app/editor@1.0.3`, not a mock editor. Upstream: https://github.com/pascalorg/editor (MIT license).

Run: `cd integrations/pascal-studio && npm install && npm run dev`.

**Verification boundary:** dependency installation, browser rendering, and scene-to-AirTrajectory LayoutContract conversion have **not** been validated here. The production, dependency-free US1 editing slice is at `web/studio.html`. This Pascal host is a deliberate migration seam, not yet a usable physics input. Before making it the canonical editor, implement a tested scene import/export adapter with stable entity IDs, room/wall/opening adjacency and metric units; validate by round-trip against the Python LayoutContract and do not treat 3D geometry as engineering-approved airflow data.
