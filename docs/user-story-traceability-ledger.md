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

## 2026-10-09 — P0 solver-evidence boundary checkpoint

- Added `airtrajectory/imported_contam_readiness.py`: combines portable topology acceptance with actual `compile_contam_ir` readiness, names the output `COMPILE_READINESS_ONLY_NOT_SOLVED`, and binds positive readiness to the real `contam_semantics_sha256`. Missing metric geometry is BLOCKED, not PASS.
- Added `tests/test_imported_contam_readiness.py`: missing metric input rejection, positive metric-complete symbolic IR, and fixed demo rejection. Also extended `tests/test_layout_correction.py` with canonical JSON roundtrip and runtime assertions.
- Evidence classification: toy topology PASS != ContamX simulated output != physical hardware measurements. D-P0-001 remains OPEN until real PRJ generation, actual solver run, immutable receipt, and browser integration for the same imported topology.
- Latest PR #222 head must pass Core and Pages CI before merge. No complete Story 01/02 closure claimed.

## Horizontal completeness audit — 2026-10-09

- Added machine-readable `docs/user-story-horizontal-matrix.json` with **all 15 canonical stories × 10 dimensions**, deliberately conservative statuses. A fully populated audit record is NOT proof of story completion.
- Added `airtrajectory/horizontal_audit.py` and `examples/audit_user_stories.py`: reject missing dimension/evidence/rationale; fail any `VERIFIED_CLOSED` claim without all applicable dimension evidence, independent/vertical evidence or closed upstream dependencies. `python examples/audit_user_stories.py --out artifacts/story-horizontal-audit.json`.
- Added `tests/test_horizontal_audit.py` with independent negative tests for fake closure, missing status/evidence, unavailable N/A rationale and incomplete dependency closure. CI for latest PR SHA remains the gate.
- Dependency graph is explicitly an **engineering interpretation** derived from user-story acceptance flows, not a new product requirement. Update mapping when real user story history disproves an edge.
- External option review (official docs, 2026-10-09): NIST CONTAM 3.4 / 2026 CONTAM APIs https://www.nist.gov/el/beed/nist-multizone-modeling/software/contam/contam-documentation ; IfcOpenShell geometry/spatial tools https://docs.ifcopenshell.org/ifcopenshell-python/geometry_processing.html . Prefer validated adapters, not a custom IFC geometry kernel / airflow solver. No dependency replacement until license/version/API and independent integration tests are recorded.
- Remaining D-P0-001: browser imported layout → actual CONTAM solve still absent; IR readiness explicitly **not** a solver run. D-P0-002: visual correction remains incomplete. D-P0-003: varied imported topology actual CONTAM tests absent.

## Horizontal audit implementation and external-option decision — 2026-10-09

- Added `impacted_stories(changed)` to compute transitive downstream impact based on the declared engineering dependency DAG. Regressions in imported-layout Story 1 therefore require review of all fifteen downstream story evidence records. This is an impact **list**, not automatically a completed regression run.
- External option `IfcOpenShell 0.9.0`: upstream project documentation https://docs.ifcopenshell.org/ifcopenshell.html and release index https://pypi.org/project/ifcopenshell/ ; Python >=3.10 <3.16; LGPL-3.0-or-later. Existing parser and adapters should be compatibility-tested against pinned wheels before optional upgrade. License compliance and distribution mode not yet signed off.
- External option `NIST CONTAM 3.4.0.1`: official https://www.nist.gov/services-resources/software/contam ; ContamX runs on Windows and Linux; NIST-developed components are US public domain, with derivative notice and experimental-system caveats. API paper (2026-01-30) https://www.nist.gov/publications/development-and-application-contam-apis describes dynamic control/query possibilities, but this repo has not integrated or benchmarked that API; do not claim compatibility.
- Selection: **retain present working adapters**; assess external geometry iterators and CONTAM API via pinned optional integration probes before replacement. Do not add dependencies purely because they are more recent.
- The horizontal audit records may pass consistency rules while all product stories remain `PARTIAL`/`BLOCKED`. Never treat a green audit-record command as Story PASS.

## 2026-10-09 — Canonical identity fail-closed checkpoint

- P0 input contract defect found: `LayoutContract.validate` previously accepted whitespace-only room/wall/opening IDs and a room ID equal to `outside_id`. These invalid identities risk ambiguous topology and solver mapping. Fixed in commit `c359ad0f59509052421e49346e232a081f3bae38`.
- Added independently specified negative regression cases in `tests/test_canonical_identity.py` (commit `8344d42747ff1fe2b69ff8e16c812a185e7a83a7`).
- Evidence gate: `python -m unittest tests/test_canonical_identity.py -v` (or discovery mode); latest head Core workflow https://github.com/hippoley/AirTrajectory/actions/runs/37881456450; Pages workflow https://github.com/hippoley/AirTrajectory/actions/runs/37881456508. Both were **QUEUED at inspection**. No PASS until run results are read.
- Scope boundary: this corrects ID validation only. It does not establish imported topology → generated PRJ → real ContamX run, graphical editing, independent unfamiliar-layout solve, or any Verified Closed story.

## 2026-10-09 — Runtime override non-finite rejection checkpoint

- Found a cross-story state-to-physics trust boundary: `DemoRuntimeSnapshot.resolve()` range checks accepted NaN because IEEE comparisons with NaN are false. Both opening position and actuator opening state overrides now explicitly require finite values (commit `a608dce25d4a54041fac818ea25e2284769d7ce8`).
- Added counterexamples for NaN, positive infinity, negative infinity, plus acceptance of legitimate finite boundary values (commit `386c6a9073a831e85fb7b13f6f633e0348f80942`, `tests/test_runtime_nonfinite_overrides.py`).
- Required verification: run the new tests and existing full Core workflow against the *current* PR head. Code push alone is not a test verdict. Relevant stories: 1, 2, 5, 6, 15 and other reachable consumers of runtime snapshots.
- Evidence limit: no real imported-layout ContamX solve, browser editor acceptance or independent unfamiliar-topology numerical receipt was produced by this change; D-P0-001/002/003 remain OPEN.

## 2026-10-09 — Imported PRJ demo-profile isolation gate

- Found P0 integration safety gap: `examples/generate_multispace_contam_prj.py --layout unfamiliar.json` could inherit fixed-demo metric, boundary, PRJ and illustrative airflow profiles. Profiles might not match imported IDs and should never silently be considered real project data.
- Imported layouts now **require explicit command-line supply** of all four profiles, including a newly supported `--airflow-profile` option. Fixed demo defaults remain unchanged. Commit `401920d685eef416a0c43eef71b37eb910a2f9c8`.
- Added an independent CLI negative test asserting an imported topology with omitted profiles cannot emit a PRJ (`tests/test_imported_prj_cli_safety.py`, commit `116b9a9ba61ed9c7d1abf06168764d4c2c082c03`).
- This is a fail-closed integration guard, **not** imported-layout solver evidence. Acceptance still requires independent layout-profile compatibility, real ContamX runtime on newly generated PRJ, numerical result validation and immutable provenance. D-P0-001/003 remain OPEN.

## 2026-10-09 — Imported geometry profile revision binding

- A stale profile could match `topology_id` and all room/wall/opening IDs despite a revised layout (e.g. edited room volume). Imported metric overlays now require `layout_contract_sha256` to equal the **current base LayoutContract** hash; optional hashes on fixed demo overlays are also checked. Change: `ff8a0b86cf5977582f0370f1b2a890b35a778a07`.
- Expanded `tests/test_contam_metric_overlay.py`: reject missing hash, accept matching hash, and independently mutate room volume while retaining topology/entity IDs to verify stale-hash rejection. Change: `cde675634b40b2bc2e524f5b3eeee3c3260e1bf6`.
- This is a source-to-metric binding integrity guard, not an engineering-validation claim. Imported CLI users must supply a profile derived from their exact source layout, including this fingerprint. Actual foreign-layout PRJ serialization, ContamX execution and browser workflow remain unverified.

## 2026-10-09 — Failing Core CI: duplicate prediction-steps counterexample

- For PR head `8fbb55c320382ad1eb8d42e5b87d9a5014df4d6f`, Core CI run https://github.com/hippoley/AirTrajectory/actions/runs/37882284237 failed: 701 tests, 1 failure. `contam-real` job passed separately; Pages run https://github.com/hippoley/AirTrajectory/actions/runs/37882284454 succeeded.
- The failing test `test_reject_duplicate_runtime_prediction_steps` mutated `prediction_series[1].step` but left both `prediction_series_sha256` and `runtime_receipt_sha256` stale; hence the runtime integrity gate correctly rejected it before the duplicate-step semantics gate.
- Fix commit `acdb61d1a913f9d528180c5dfcfaf5d7117e37f9` rebinds both hashes after mutation, preserving integrity validation while making the semantic duplicate-step rejection reachable. The current working branch previously lacked this test from the newer main; it now includes the main test collection plus the corrected case.
- Verification remains **PENDING** for the updated head until new Core CI confirms the changed test and full suite. No claims of Story Verified Closed; D-P0-001/002/003 are unchanged.

## 2026-10-09 — CI independent rejection fix and current NIST version check

- Previous Core CI on PR #222 failed 1/701 tests due to an unsigned mutation in the duplicate-step counterexample. Test was repaired in `acdb61d1a913f9d528180c5dfcfaf5d7117e37f9` by recomputing both prediction-series and outer runtime receipt hashes before asserting semantic duplicate rejection.
- Cross-branch comparison revealed that the PR branch validation implementation also lacked the duplicate-step check present on newer `main`. Added explicit duplicate detection before constructing the dictionary of predictions in `airtrajectory/contam_field_validation.py`, commit `b2a772161fadacee5b6690081644675585e37bea`. This prevents duplicate entries being silently overwritten even when hashes are valid.
- NIST official download page (checked 2026-10-09): https://www.nist.gov/el/beed/nist-multizone-modeling/software/contam/download-contam lists CONTAM release 3.4.0.8 (2026-01-08), with ContamX executable 3.4.0.3. The 2026-01-30 CONTAM API publication describes interactive execution/query, but neither is evidence that this branch executes unfamiliar imported topologies.
- Acceptance gate: latest full Core and `contam-real` workflow must pass. No Verified Closed status until the user-level imported-layout solver receipts and independent cross-story E2E are obtained.

## 2026-10-09 — Dataset/Benchmark horizontal integrity upgrade

- Benchmark review found `unseen_topology_benchmark` trains on 2–4 room **chain** families and evaluates 5-room **chain** families. This is unseen-size extrapolation, **not** held-out graph-family generalization. Prior results must not claim transfer to branching/hub/loop plans.
- Commit `70b801701fd6b141914d748ba9bc72f6cb0894de` adds explicit training/test scenario seed manifests, SHA-256 split identity, collision rejection, matched-seed mean policy return deltas vs rule baseline, and `TOY_ONLY_NOT_CONTAM_OR_FIELD` classification. Outputs record `held_out_topology_families: false`.
- Commit `7873c4175fc21088fc7717165a193c558fa87d65` adds independent `tests/test_benchmark_reproducibility.py` cases checking paired seeds, split fingerprints, evidence boundary and invalid arguments.
- Evaluation limitations: default test_count=8 is too small to claim robust superiority; the paired deltas are descriptive, not confidence intervals. Hold out structural topology families, add multiple repeated splits and uncertainty intervals, and evaluate matched alternative policies on engineering-grade ContamX before claiming generalization. Training rows still include rule behavior only; BC and OfflineQ are baselines, not proven better policies.
- External comparison: Farama D4RL now directs new offline dataset development to Minari (https://github.com/Farama-Foundation/D4RL); follow dataset structure/provenance and avoid blind migration without licensing/version/integration tests. NIST's 2026 CONTAM APIs (https://www.nist.gov/publications/development-and-application-contam-apis) are a candidate for future physically grounded evaluation, not current benchmark evidence.
- Current status: implementation and negative tests submitted, latest Core CI **pending**; Story 11/12/14 remain PARTIAL; D-P4-001 remains OPEN. No real-contam imported-layout or field evidence was produced.

## 2026-10-09 — Held-out structural topology benchmark upgrade

- Added deterministic non-chain toy topology families (`hub`, `loop`, `branch`) with explicit internal-door graph structure in `airtrajectory/scenario.py`. Commits `0a3ad7e04b2100330eef70c9ff1aa9acfdee91af` and branch topology correction `b4515bfc183375dd99b17030aa3bcb2bdcad3a3a`.
- Added `held_out_family_benchmark()` in `airtrajectory/benchmark.py`, commit `1b1fc90551d94b2a05156e96b2d80ece4cfb25bc`. It trains BC and Offline Q on chain 2–4-room examples and independently reports 5-room hub/loop/branch evaluation, per-family summaries, paired return deltas against rule, reproducible split hash and scenario seeds.
- Added `tests/test_structural_generalization.py`, commit `af328a19067e81595ab2e19690f211c77b5dcba5`: checks exact five-room graph degree sequences (star=[1,1,1,1,4], cycle=[2,2,2,2,2], fork=[1,1,1,2,3]), deterministic edges, train/test seed separation and Dataset transition provenance.
- This is a structural toy benchmark only (`TOY_ONLY_NOT_CONTAM_OR_FIELD`); it is **not** a real imported building sample, physical model, independent field validation or statistical superiority claim. Cross-family invariants do not prove that physical distributions match.
- **Status: PENDING CI / independent execution**. Preserve D-P4-001 as PARTIAL until results, repeated seeds with uncertainty intervals, adversarial physical scenarios and real ContamX validation exist. Story 11, Story 12 and Story 14 remain PARTIAL.

## 2026-10-09 — Execution-mode switch: vertical product integration

- **Active delivery contract:** [Product Mainline Integration and Independent Acceptance](product-mainline-integration-acceptance.md), introduced by commit `92cb8feead313fa85044cb18e8cbf9de8d7e2bf3`.
- Stop prioritizing scattered defect hunts and standalone benchmark features. Only fix failures directly blocking the integrated journey or evidence correctness.
- Next acceptance target: two previously unfamiliar layout inputs → browser correction/reload → revision-bound PRJ → **native ContamX execution** → real numeric receipt. Follow with matched-origin HOLD/Independent/Joint comparison and user-visible provenance.
- This policy change does **not** close D-P0-001/002/003 or any individual user story; status remains INTEGRATION_INCOMPLETE pending runnable independent evidence.
