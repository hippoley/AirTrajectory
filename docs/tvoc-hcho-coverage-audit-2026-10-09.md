# TVOC and formaldehyde support audit — 2026-10-09

Original requirement boundary: US3 environmental state and US4 user goals; US6/7 real multi-pollutant forecasting and competing goals remain unverified.

## Actual implemented coverage
- Already existed before this change: `tvoc_ug_m3` and `hcho_mg_m3` in `environmental_state.py`, JSON Schema, semantic Haystack crosswalk, and `PollutantGoal`. **Do not describe them as newly invented fields.**
- Added priority terms `tvoc_excess` and `hcho_excess` in `objective.py`. Both require corresponding declared pollutant goals, and are independently ranked in the supplied-future comparer.
- Added a fail-closed test that an objective requiring TVOC/HCHO refuses CO2-only trajectories. No value is inferred from CO2.
- Added unavailable HCHO to the example; TVOC was already unavailable. Unavailable fields do not inflate measured fraction.
- Added concentration constraints for both indoor fields and NaN/Inf rejection for EnvironmentalValue, without rejecting legitimate negative Celsius.
- Units: TVOC in micrograms per cubic metre, formaldehyde in milligrams per cubic metre. Preserve these as distinct channels. A raw sensor reading in ppb or ppm requires substance-specific calibration/conversion with temperature/pressure context, not blind renaming.

## Double layer acceptance
| Dimension | State | Evidence boundary |
|---|---|---|
| Function | PARTIAL | State and objective priority path connected |
| State | PARTIAL | Nullable values and separate sources preserved |
| Integration | BLOCKED | No real TVOC/HCHO adapter or calibrated physical output exercised |
| Safety | PARTIAL | Reject nonfinite/negative concentrations, reject missing trajectories |
| Performance | NOT VERIFIED | No source/sensor scale benchmarks |
| Maintenance | PARTIAL | Existing schema reused; no new dependency |
| Observability | PARTIAL | Evidence class and source id supported |
| Testing | PENDING | Tests committed; require passing HEAD CI |
| User value | PARTIAL | Can represent readings and objectives, cannot promise an actuator response |
| External compatibility | NOT VERIFIED | Upstream Haystack crosswalk exists, no live connector validation |

**No solver-side prediction claim.** Real CONTAM contaminant model needs source terms, outdoor boundary, deposition/removal and trustworthy per-species parameters before `simulated` results are promoted. A source may report total VOC on a reference calibration scale; it must not be treated as a substance-specific health risk signal or interchangeable with HCHO.

Resume: latest HEAD CI plus end-to-end sensor fixture -> canonical state -> ObjectiveContract -> verified physics forecast -> cross-policy comparison (not yet achieved). No new P0 user story is formally closed.

## Cross-story regression follow-up
- CI `37891805084` had 682 tests, one failure in duplicate-runtime-step adversarial fixture. The injected step mutation did not rehash the runtime receipt, so the existing digest guard rejected it before the duplicate-step guard. This was a **test fixture bug**, not proof that the new TVOC/HCHO comparator failed.
- `e7513b7360` fixed the fixture by recomputing both `prediction_series_sha256` and `runtime_receipt_sha256` after deliberate mutation, so the negative test exercises its intended validation boundary.
- New HEAD workflow https://github.com/hippoley/AirTrajectory/actions/runs/37892169280 was queued at last inspection. Leave US3/4/6/7 and cross-story P0 open until it passes and physics integration evidence is collected.
