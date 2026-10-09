# Third-party components

AirTrajectory maintains its own product branding. Reusing third-party implementations does not require showing their product names in the main editor UI, but must preserve copyright and license obligations.

## openPlan3D wall projection

- Source: https://github.com/laanlabs/openPlan3D
- Original file: `src/lib/utils/wallProjection.ts`
- Local adaptation: `web/vendor/openplan-wall-projection.js`
- License: MIT
- Changes: TypeScript-to-JavaScript adaptation; mapping AirTrajectory `x1/y1/x2/y2` wall coordinates, browser + Node export wrapper, geometry regression tests.

MIT License

Copyright (c) 2026 theLodgeStudio

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.


## Other editors evaluated, not copied

- Pascal Editor: https://github.com/pascalorg/editor — MIT; optional host uses npm package, separate from the current production studio.
- blueprint-js: https://github.com/aalavandhaann/blueprint-js — MIT; geometry architecture reference only.
- floor-planner: https://github.com/RobinWeitzel/floor-planner — check licensing of exact source before copying; no code vendored in this change.
- tldraw: https://github.com/tldraw/tldraw — licensing requires case-by-case review; no code vendored in this change.

Do not remove third-party notices when distributing this repository.
