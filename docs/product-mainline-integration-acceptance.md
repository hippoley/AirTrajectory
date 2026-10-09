# Product Mainline Integration and Independent Acceptance

Status: ACTIVE EXECUTION POLICY, 2026-10-09. This document specifies delivery gates, not completion claims.

## North-star product journey
Unfamiliar home import → browser correction and save/reload → edited LayoutContract → revision-matched engineering profiles → generated PRJ → native ContamX run → same-origin HOLD / Independent / Joint comparison → UI result → immutable evidence receipt.

Stop prioritizing isolated validators, cosmetic tests and speculative benchmarks. Only fix defects that block this journey, critical safety, or the credibility of results. Reuse mature components already in the repository instead of rewriting the solver.

## Vertical delivery gates
| Gate | Acceptance evidence | Current status |
| --- | --- | --- |
| V0 Import | Unfamiliar JSON/IFC to canonical topology, source hash, variable room/opening IDs | PARTIAL |
| V1 Correct | Browser graphic edits, operation replay, save/reload, edited layout hash | BLOCKED |
| V2 Compile | Current geometry revision binds all four profiles and yields exact source-matched PRJ/IDs | PARTIAL |
| V3 Native solve | Exact imported PRJ executed by native ContamX, correct zone/path counts, finite numerical outputs and version receipt | BLOCKED |
| V4 Compare | HOLD + Independent + Joint all simulated from identical immutable origin and horizon, per-metric outcomes | BLOCKED |
| V5 Display | UI shows each physical result, unsupported signals, errors and original topology revision without stale predictions | BLOCKED |
| V6 Evidence | Source/correction/layout/profile/PRJ/backend/result hashes, commit, CI run and independent replay | BLOCKED |

P0 integration milestone requires V0 through V3 plus V6 for at least two independently supplied unfamiliar layouts. Product comparison additionally requires V4 and V5. Passing one milestone does not waive any original story acceptance criterion.

## Required independent negative tests
- A new layout with different room/opening counts; a second layout with branching or cyclic connectivity.
- Missing dimensions, duplicated IDs, stale geometry overlay, wrong profile opening keys and source-revision drift fail closed.
- Solver missing, timeout, nonzero exit, malformed numerical output and changed backend version cannot yield a successful receipt.
- Topology edits invalidate previous trajectory forecasts, cache and displayed UI results.
- HOLD is a simulated no-action future, not an unmodified snapshot; all comparisons have the same origin and horizon.
- Physical measured evidence may not be inferred from a toy simulation, generated PRJ, fake device or a successful CI job.

## Horizontal matrix and story intersections
Track function, state, integration, security/correctness, performance, maintainability, observability, tests, user value and external compatibility. Each applicable dimension needs linked evidence and a status; N/A needs an explicit reason.
Story 1 edit impacts Story 2 IDs and Stories 5/6/15 planning and display. Story 2 variable topology impacts compiler, action set and dataset. Stories 11/12/14 benchmark claims stay toy-only until externally validated native runs; real hardware Stories 8/9 remain blocked until authenticated readback.

## Independent verification
An author other than the implementer supplies unfamiliar layouts and adversarial profiles. Reproduce the full browser-to-solver journey, compare result and source hashes, independently inspect one physical output, inject a solver failure, and attach real logs and CI job links. Developer tests and PR state alone never establish Verified Closed.

## Delivery order / stop conditions
1. Resolve Core CI and reconcile branch with current main; never suppress integrity failures.
2. Deliver an independent imported-layout real ContamX smoke path and archived native solver receipt.
3. Connect browser edit/save/load to backend revision-bound generation, simulation and error display.
4. Compare HOLD/Independent/Joint from identical physical origin; archive reproducible receipts.
5. Run two unfamiliar layouts, failure injection, regression and independent verifier; promote only fully evidenced original stories.

Every new change must identify a gate it unblocks and a before/after reproducible test. Unrelated defect hunts are deferred. Current product verdict: INTEGRATION_INCOMPLETE.