# Dataset / Benchmark horizontal audit — 2026-10-09

## Scope and acceptance
Canonical stories US10 (prediction-error learning), US11 (unseen topology), US12 (reproducible benchmark), US14 (post-training). This iteration fixes **split leakage and reproducibility in the existing toy benchmark**, not verified real-physics performance.

## Implementation
- `airtrajectory/benchmark.py`: require positive integer counts/horizon, nonnegative integer seed, disjoint training/testing scenario seeds **before any episodes are generated**, and export the explicit train/test seed manifest, split unit and same-test-origin declaration.
- `tests/test_learning_benchmark.py`: assert exact heldout manifest and disjointness; reject fractional/boolean/zero parameters and an intentionally overlapping train/test seed range.
- The training suite presently uses chain-generated 2–4 room toy scenarios and tests chain-generated 5-room toy scenarios. This is a **room-count holdout only**, *not* a family/structure holdout; `toy_ablation.py` implements a separate, explicitly labeled toy structural-family experiment. Do not mix these claims.
- Seed separation alone does not establish group independence across duplicate geometry, parameter presets, synthetic scene generators, temporal neighbors, or calibration records. Future real-physics corpus needs group-aware splitting at building/geometry/source-family level, with solver revision, PRJ checksum, scenario fingerprint, time grid, source terms, calibration provenance, policy budget and held-out family recorded.
- `dataset.transition_rows` retains executed actions versus proposals and preserves sensor/effect provenance; counterfactuals remain separately labeled. Existing contracts are reused, with zero new dependencies.

## External technical comparison
- scikit-learn GroupKFold: https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupKFold.html (non-overlapping groups). No sklearn dependency is needed for this deterministic seed-only guard; consider GroupKFold/GroupShuffleSplit when actual building grouping exists.
- NIST CONTAM: https://www.nist.gov/services-resources/software/contam ; official multizone airflow + contaminant transport engine. This project already exercises official ContamX in CI; do not replace it with a toy simulation or claim that an available CO2 run predicts TVOC/HCHO.

## Ten-dimension audit
| Dimension | Status | Evidence boundary |
| --- | --- | --- |
| Functional | PARTIAL | deterministic room-count holdout and manifest |
| State | PARTIAL | split seeds and policy origin recorded |
| Integration | PARTIAL | toy-learning/rollout pipeline exists; no real-physics training loop |
| Safety/correctness | PARTIAL | collision and invalid parameter fail closed |
| Performance | NOT VERIFIED | no scaling benchmark of dataset group splitting |
| Maintainability | PARTIAL | stdlib, no dependency, existing interface |
| Observability | PARTIAL | explicit seed manifest, still missing canonical scene fingerprints |
| Testing | CI PENDING | tests committed; check latest HEAD CI |
| User value | BLOCKED | unproven field performance improvement |
| External compatibility | PARTIAL | standard group-split practice reviewed; independent reproduction missing |

Two-layer closure remains **NOT VERIFIED** for US10/11/12/14. Passing toy regressions = E1/E2 only. Real solver E3, field E4 and non-owner adoption E5 are separate.

## Independent score-replay falsification update
- Existing dataset split patch `6543e8435` passed software CI: https://github.com/hippoley/AirTrajectory/actions/runs/37895269892.
- `103bc7ef5` now recomputes CO2 excess, peak, final worst-zone, threshold exceedance counts from recorded frames, and recomputes per-policy aggregates from per-episode metrics. It rejects nonfinite or negative frame CO2.
- `421b4e226` introduces *resealed tamper* tests: an attacker changes BC episode peak or aggregate mean, then recomputes the overall SHA-256; the verifier must reject semantic discrepancies. This differentiates checksums from independently checked content.
- These checks validate *internal consistency* of toy replay, not independent solver execution nor data authenticity. Source replay, physical solver identity, true train/building-family holdout and E4 field calibration remain open.
- Latest test workflow: https://github.com/hippoley/AirTrajectory/actions/runs/37896093572 ; status pending at inspection.
