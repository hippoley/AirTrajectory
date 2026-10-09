# P0 horizontal validation: non-finite field evidence (2026-10-09)

Canonical User Stories: US3 environmental state, US8 real actuation evidence, US10 prediction error learning; downstream US9, US12, US14. Source: `docs/product-user-story.md`; original evidence audit: `docs/user-story-evidence-audit-2026-10-09.md`.

## Defect and action
- Observed implementation: `airtrajectory/contam_field_validation.py` converted source floats then used comparisons like `0 <= x <= 100`; IEEE 754 NaN defeats ordered range comparisons. Missing finite checks also applied to protocol tolerance, sample interval and skew.
- Code correction: `cf1f56a9` rejects non-finite protocol thresholds, alignment durations, fixed/measured opening positions and CO2 samples.
- Independent regression: `9f6a04c6` injects NaN/+inf into these inputs, while retaining existing valid field fixture tests.

## Double closure / cross-story audit
| Axis | Current status | Evidence limit |
|---|---|---|
| Functional validity | PARTIAL | New checks are in code but latest test workflow pending |
| State consistency | PARTIAL | Invalid values rejected before normalizing receipt; no device state transaction proven |
| System integration | PARTIAL | Same field validator is used; full pipeline runtime not re-executed |
| Security/correctness | PARTIAL | New input rejection and adversarial test cases |
| Performance/scale | NOT VERIFIED | Constant-time scalar guards, no real deployment benchmark |
| Maintainability | PARTIAL | Existing standard library math.isfinite; no new dependency |
| Traceability | PARTIAL | Two commits; awaiting CI result and field receipt |
| Testability | PARTIAL | Positive fixture and negative tests committed; CI pending |
| User value | BLOCKED | No measured commissioned physical evidence yet |
| External compatibility | NOT VERIFIED | No external package introduced or protocol interoperability re-run |

**Acceptance state: NOT CLOSED.** Do not claim E4 measured field evidence or real predictive validation from simulated fixtures. For final closure, record passing test CI on same relevant commit plus genuine site-measured capture and matched predicted-origin receipts. If workflow is cancelled or queued, record this without upgrading the Story.

Cross-story impact: US3 -> US4/6/7 -> US8/9 -> US10/12/14. Re-run related physical and benchmark regression suites after the fix.

Private research repository remains a separate consumer; the correction is in the original AirTrajectory codebase. No external outreach is authorized.
