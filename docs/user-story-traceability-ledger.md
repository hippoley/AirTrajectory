# User Story traceability, defects and acceptance evidence

Audit date: 2026-10-09. **Source of requirements:** `docs/product-user-story.md` (Stories 1–15 and acceptance ladder A–H) and `docs/development-priority-contract.md` (P0–P5). No new research concept is accepted as a product requirement without source mapping.

## Acceptance policy

- `PASS`: story-specific acceptance is demonstrated by runnable, reproducible evidence and its required real-world/external gates.
- `PARTIAL`: code and/or tests exist, but at least one declared acceptance condition remains unmet.
- `BLOCKED`: indispensable hardware, evidence or independent actor unavailable; no mock substitute.
- CI passing validates a **commit**, not the entire user story. A PR opened but not merged is not on `main`.
- Development priority P0 is **arbitrary topology intake**, not a claim that every story is P0.

## Story matrix and provenance ledger

| Story | Origin / requirement intent | Implemented trace | Real acceptance missing | Status | Priority |
| --- | --- | --- | --- | --- | --- |
| 01 Import any home | Own layout; correct recognition/adjacency; canonical topology | `airtrajectory/importers/ifc.py`, `layout_correction.py`, PR #195/#218/#220/#221 | Browser visual correction; imported-topology solver run; CAD/SVG/raster support as declared | PARTIAL | P0 |
| 02 Arbitrary counts | No fixed W1/W2/W3 state/action vector | `layout.py`, `topology_acceptance.py`, `spatial_compile.py` | Multiple unfamiliar layouts through real physics execution | PARTIAL | P0 |
| 03 World state | CO2/TVOC/HCHO/PM2.5/temp/RH and provenance | Existing CO2 simulation and physical lineage | All supported signals with correct measured/simulated/unavailable semantics | PARTIAL | P1 |
| 04 Goals not actuator commands | Inspectable objectives & hard safety/comfort constraints | Rule / scalar reward infrastructure | Goal-to-typed-objective and conflict explanation | PARTIAL | P1 |
| 05 Joint topology strategy | HOLD/independent/joint from topology paths | `agents.py`, `rollout.py` | Same-origin candidates on arbitrary imported topology | PARTIAL | P2 |
| 06 Multiple futures | Same immutable origin/horizon and per-metric effects | Counterfactual branch runtime | Actual same-origin multi-environment alternatives, trusted horizons | PARTIAL | P2 |
| 07 Conflicting objectives | High indoor CO2 with high outdoor PM2.5 | No accepted multi-species physics comparison on main; #202 closed unmerged | Real modeled tradeoff can select HOLD/bounded intervention | PARTIAL | P1/P2 |
| 08 Physical execution | ACK != readback; conservative actuation | WindowPilot adapter and `physical.py` | Real hardware commissioning and measured physical τ0 | BLOCKED | P3 |
| 09 Replan on changed reality | Invalidate old assumptions / measured new origin | `rollout.py`, field handoff logic; PR #219 | Real multi-step measured replan | PARTIAL | P3 |
| 10 Learn from error | Save predicted versus measured outcomes | `dataset.py` | Demonstrate calibration and held-out improvement | PARTIAL | P3 |
| 11 Generalize unseen layouts | Scale, structure, environment and device transfer | `benchmark.py` unseen 5-room chain | Held-out branching/hub/loop structural-family results | PARTIAL | P4 |
| 12 Research benchmark | Shared metrics, provenance, HOLD/independent/joint/learned | `benchmark.py`, dataset export | Independent multi-backend reproducibility & per-metric comparisons | PARTIAL | P4 |
| 13 Third-party infrastructure | Others adopt contracts without product | `layout.py`, trajectory contracts and adapters | Independently verifiable outside project adoption | BLOCKED | P5 |
| 14 Trajectory post-training | Rule → BC → Offline RL, prove incremental improvement | `learning.py`, `dataset.py`, `benchmark.py`; #215 open experimental tooling | Same-origin held-out ablations without safety regression | PARTIAL | P4 |
| 15 Playable exploration lab | User changes topology/objectives and inspects causal futures | `web/lab.js`; PR #218/#219 | Imported-home interactive correction and regenerated physics, all requested baselines | PARTIAL | P0/P2 |

## Historical decision and engineering lineage (verified PRs)

- #195 **merged**, strict public IFC import/readiness; public IFC and core CI green. Rejected unsupported geometry rather than fabricating metric quantities.
- #202 **closed unmerged** despite green CI. Candidate multi-environment scoring is NOT on main. Static HOLD was corrected to a non-forecast snapshot; do not report story 6/7 PASS.
- #215 **open** with green CI: provenance replay preparation, not proof of post-training gains. Not on main.
- #218 **merged**, imported-layout correction and browser JSON intake. Core and Pages CI green.
- #219 **merged**, clears stale predictions after topology changes; Core and Pages CI green.
- #220 **merged**, explicit room/wall add/remove and referential integrity; Core and Pages CI green.
- #221 **merged**, explicit room split requiring complete incident wall ownership; Core and Pages CI green.
- Current PR #222: explicit room merge, non-finite geometry rejection, topology-runtime and JSON roundtrip tests, and this ledger; no success can be claimed until CI and integration verification.

## Open defect register

| ID | Severity | Evidence | Required closure |
| --- | --- | --- | --- |
| D-P0-001 | P0 | Browser imported JSON is not passed to an executable solver in the browser product | Full import→correct→physics→trace receipt on a new topology |
| D-P0-002 | P0 | Browser lacks full graphical room/wall editing and save/load of correction ops | Interactive split/merge/reposition and round-trip acceptance |
| D-P0-003 | P0 | Story 2 lacks demonstrated arbitrary imported topology through engineering-grade CONTAM run | Verified generated PRJ and physical engine output on independent imports |
| D-P1-001 | P1 | #202 unmerged; CO2-only claims insufficient for multi-pollutant scoring | Verified environmental source models, comparable branches, hard safety constraints |
| D-P2-001 | P2 | Static HOLD is not a simulated no-action future | Same-origin same-horizon solver HOLD run |
| D-P3-001 | BLOCKED | Real WindowPilot commissioning and physical τ0 not captured | Authenticated live measured readback/closeout, no mock promotion |
| D-P4-001 | P4 | Test family is chain-only | Unseen graph family benchmark and safety gates |
| D-P5-001 | BLOCKED | No independent external consumer shown | External repository, citation, reproduction or compatibility request |

## Evidence and next entry point

1. Start with [PR #221](https://github.com/hippoley/AirTrajectory/pull/221) merged and [PR #220](https://github.com/hippoley/AirTrajectory/pull/220) merged; retain immutable commits in the PR history.
2. Inspect the latest PR against this register; run `python -m unittest discover -s tests -v`, the browser JS check and a manual import smoke test.
3. Complete D-P0-001/002/003 before approving the Arbitrary-layout MVP (acceptance ladder B). Do not relabel a `verify_topology_runtime()` toy roll-out as validated CONTAM output.
4. For each closed defect, append **commit SHA + workflow link + runnable command + output receipt + scope boundary** here.
5. Any historical story or acceptance clause newly found in repository history must be added here and mapped before claiming complete coverage.

**Audit limit:** This ledger traces the current full 15-story requirement document and verified selected PR history. It is not yet an exhaustive forensic reconstruction of every earlier commit/issue; historical completeness remains an open audit item.

## 2026-10-09 execution checkpoint

- PR #221: merged as `1dd037c8cdd652c586f5785b96afeee48b39036c`; both required workflows passed; room split sub-capability only.
- PR #222: active, latest development includes `merge_rooms`, `LayoutContract` finite-number validation, tests for cross-module `verify_topology_runtime`, unknown/shared walls, NaN/Infinity and canonical JSON roundtrip. Workflow verdict must be checked for the latest head before merging.
- D-P0-001 remains **OPEN**: topology runtime verification uses a toy rollout and cannot substitute for imported-layout actual CONTAM execution.
- D-P0-002 remains **OPEN**: code-level correction operations do not satisfy interactive graphical room/wall editing.
- Story 08 **BLOCKED** on field evidence; Story 13 **BLOCKED** on third-party adoption. No simulation or PR is a replacement.
