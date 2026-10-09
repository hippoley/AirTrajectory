# AirTrajectory — 2026-10-09 product/reality evidence audit

**Scope:** current `main` at `96d7d208ff996ce999cc8a89b9f56cb5f001f528`.
**Canonical acceptance:** [product-user-story.md](product-user-story.md), US1–US15.
**Principle:** a merged contract is not a completed user journey, a real
ContamX run is not a physical window measurement, and same-owner reuse is
not independent adoption.

## Executive verdict

The repository has three promising durable seams:

1. **Open building model → physical-control readiness → canonical topology.**
   Public IFC regression exists, including explicit BLOCKED results for
   missing opening-to-space evidence. #195.
2. **Topology → portable VentilationPath → physics/policy consumer.**
   A standalone topology-bound path contract and CLI now exist. #194.
3. **Same-origin policy benchmark → inspectable environmental objective
   → bounded physical-origin lineage.** Real ContamX HOLD/Independent/Joint
   CO2 benchmarks (#191), fail-closed objective semantics (#203), and
   backend-to-objective *toy first-step* replay (#208) now exist.

These are **proofs of implementation**, not yet proof of industry position.
No verified non-hippoley consumer, field-actuated tau0, multi-pollutant
CONTAM future or real-physics post-training advantage was found in this audit.

## Evidence ladder

| Level | Evidence | Permitted claim |
| --- | --- | --- |
| E0 | docs/architecture | proposal only |
| E1 | schema/unit tests | local semantic validity |
| E2 | deterministic toy backend | algorithm plumbing/transfer *in toy physics* |
| E3 | real ContamX/IFC public corpus | verified engine execution or public-model compatibility within the tested scope |
| E4 | commissioned actuator + fresh measured sensors | bounded field control / measured next origin |
| E5 | independent non-owner retained compatibility test or adapter | first credible external dependence |

An E3 simulator receipt is never promoted to E4; an E1/E3 contract without
external adoption is never promoted to E5. A checksum proves content
consistency, not trusted provenance by itself.

## Fifteen user stories: exact missing acceptance receipts

| US | Current evidence | Status | Next executable closure receipt |
| --- | --- | --- | --- |
| 1 Import any home | #195 imported JSON/IFC path, public IFC2X3 readiness | PARTIAL | previously unseen user source → add/remove/split/merge rooms and move openings in UI → canonical topology → VentilationPath → physics without code edits; reject missing metric geometry |
| 2 Variable topology | variable BuildingTopology; #195 imported four-room; #207 five-room toy graphs | STRONG PARTIAL | 2/3/5+ rooms with independently imported geometry through same ContamX compiler |
| 3 Environmental state | environmental_state.py; #196 HouseZero hzconvert header adapter; #203 objectives | PARTIAL | common-zone indoor/outdoor CO2 + PM2.5 + temperature + RH with evidence classes, physically predicted by one supported backend; unavailable stays unavailable |
| 4 Goals, not raw percentages | #203 canonical ObjectiveContract; #208 backend first-step CO2 consumer | PARTIAL | user goal → inspected hard constraints → actual physics candidates → selected plan; unknown intent fails closed |
| 5 Joint topology strategies | VentilationPath discovery; #194 portable contract; real ContamX Joint | STRONG PARTIAL | imported unseen topology generates and physics-tests candidate paths, with explicit direction/effectiveness evidence |
| 6 Multi-future preview | #191 real ContamX HOLD/Independent/Joint CO2; #203 supplied multi-environment fixture; #208 toy objective UI | PARTIAL | same origin/horizon multi-pollutant backend futures and uncertainty; no static HOLD substitution |
| 7 Conflicting goals | #203 CO2/PM2.5/comfort semantic conflict fixture | SEMANTICS ONLY | actual measured/physics-backed outdoor PM2.5 boundary, joint CO2/PM2.5/thermal futures, feasible short intervention or HOLD, no invented transport |
| 8 Conservative real actuation | software ACK/readback lineage, #52 gate | FIELD BLOCKED | commissioned WindowPilot → fresh measured baseline → authorized bounded move → newer measured position + environmental readback → audited physical tau0 |
| 9 World-change replan | stale/replan software; #209 typed rain safety | SOFTWARE PARTIAL | rain/manual window/PM2.5 event invalidates plan, fresh measured origin, new physics evaluation and bounded physical action |
| 10 Prediction-error learning | dataset and toy BC/Offline-Q; #196 external header adapter | NOT CLOSED | predicted vs later measured values with provenance, calibration update, and lower held-out error without rewriting source history |
| 11 Unseen-topology generalization | #207 toy hub/loop/irregular holdouts; #195 imported layouts | TOY PARTIAL | real ContamX structural-family holdout with equal physics/action support, safety and multi-seed uncertainty |
| 12 Reproducible benchmark | #191 real ContamX HOLD/Independent/Joint portable JSON Schema + Pareto/AUC; #207 toy five-policy replay | STRONG PARTIAL | learned policy on the same real-physics benchmark, held-out families, external reproduction and non-CO2 metrics when available |
| 13 Third-party reuse | #194 path schema; #195 IFC readiness; #191 benchmark; #196 hzconvert adapter | PUBLISHED / ADOPTION UNPROVEN | one non-hippoley repository retaining an actual contract test, adapter, issue resolution or reference |
| 14 Trajectory post-training | #207 BC/Offline-Q toy replay; #208 first-step comparison | HYPOTHESIS UNPROVEN | matched no-training agent, deterministic Joint, BC, Offline-RL on full-horizon real-physics joint-action corpus; no safety regression |
| 15 Playable truth lab | #207 interactive replay; #208 backend-derived CO2 objective table | PARTIAL | import/correct topology, set objective/weather, backend rerun, VentilationPath overlay, true field provenance, event invalidation/replan |

## Verified changes in this round

- #194 merged: portable VentilationPath v0.1, schema, CLI, tests.
- #195 merged: IFC imported-layout/readiness, public Duplex regression,
  source provenance and control-scope blockers.
- #203 merged: canonical hard-constraint/lexicographic ObjectiveContract,
  same-origin/time-grid/evidence validation, conservative rain envelope.
- #208 merged: verified toy first-step CO2 backend observations consume
  ObjectiveContract, with no invented PM2.5/thermal metrics; Pages lab table.
- #196 merged: HouseZero hzconvert canonical header adapter; CI syntax
  error repaired; missing values and out-of-range window percentages guarded.
- #191 merged: portable **real ContamX** HOLD/Independent/Joint benchmark,
  CO2 AUC/peak/time-to-safe/movement/Pareto and JSON Schema; the legacy
  independent-reference label bug was fixed before merge.
- #209 merged: typed rain safety preserves indoor-door actions rather than
  treating every opening as an exterior window.
- #202 closed **unmerged** as superseded by #203 + #208; do not publish
  competing weighted user-objective semantics.

All seven merged PRs had passing final PR-head Core and Windows ContamX
regression checks where applicable, plus Pages checks. Some intermediate
main-branch workflows were cancelled by newer commits; do not mislabel
cancelled runs as test passes or test failures. Main-head checks are
tracked separately.

## Architectural drift and remaining failure modes

1. **Product semantics vs physics:** #203's illustrative multi-pollutant
   fixture is not a solver. #208's actual backend bridge is CO2-only and
   first-step. Do not combine them to claim a physically validated
   multi-environment controller.
2. **Benchmark fairness:** #191 is real ContamX and model-agnostic but
   currently compares HOLD/Independent/Joint, not learned policies. #207
   compares five policies in toy physics. The missing common denominator is
   a real-physics learned-policy experiment.
3. **HOLD safety:** in rain, a window already open cannot be accepted as
   a feasible HOLD by #203's objective. #209's action resolver does not
   spontaneously close an initially open exterior window when no action
   is proposed; field interlock commissioning remains necessary.
4. **Geometry:** #195's imported source has stronger semantics but the
   main browser remains fixed-floorplan. IFC adjacency/readiness PASS
   does not imply that geometry is suitable for CFD/CONTAM airflow.
5. **Model replaceability:** policy checkpoints are replaceable; portable
   topology/path/objective/benchmark contracts, validated solver
   fixtures, field lineage and independent compatibility are the durable
   assets. Do not claim a novel neural architecture without ablation.
6. **External position:** own-repository issues, own CI and own cross-repo
   integrations are not independent third-party dependence.

## High-leverage execution sequence

**Next vertical slice:** choose a previously unseen *imported* layout that
passes readiness, compile it to a real ContamX test model with recorded
geometry assumptions, and produce same-origin HOLD/Independent/Joint
trajectories. Feed **only actually available** metrics to the canonical
ObjectiveContract. Emit a portable #191 benchmark receipt, then display
the same backend artifact in the lab.

**Next falsification slice:** on those same physics trajectories, compare a
joint trained candidate ranker to deterministic Joint and a matched
non-post-trained ranker. Publish negative results if learning does not help.
Keep training/test topology families disjoint.

**Next physical slice:** #52 remains reality-blocked. Do not create more
mock receipts in lieu of commissioning a window and capturing measured
position + post-action CO2/rain evidence.

**Next adoption slice:** a minimal non-owner consumer of #194/#195/#191 is
more valuable than another internal contract. The external IFC boundary
pressure case is documented in #200. A GitHub connector 403 prevented
posting a technical comment to IfcOpenShell/IfcOpenShell#1676; do not
claim upstream engagement.

## Node valuation / pivot discipline

The highest-value adjacent standards are:

- **ASHRAE 231 / OpenBuildingControl CDL/CXF:** deterministic rain,
  stale-sensor, manual-override and actuator-envelope execution shell;
  not a replacement for dynamic trajectory optimization.
- **buildingSMART IFCX / IFC Implementers Forum:** upstream test cases
  around opening-space adjacency and physical-control readiness;
  not a new IFCX module claim.
- **HouseZero / hzconvert:** independent measured environmental data
  for future calibration and validation; adapter compatibility does
  not equal dataset execution or adoption.

Do not reinvent CDL, IFC/IDS, Brick, BOPTEST or a generic building
ontology. Favor a narrow compatibility test with real upstream feedback.

**Revalue after two stable release cycles:** if no independent consumer,
no verified physics-backed post-training advantage, and no path to
measured physical tau0 emerges, freeze expansion of the standalone
AirTrajectory control product. Retain reusable readiness/path/benchmark
assets and move effort toward the externally demanded integration seam.
No arbitrary numerical ROI multiple is treated as measured fact.

## Final position statement

The next durable credential is not another repository release number.
It is an independently reproducible public-model or solver case that
another team chooses to keep, followed by a measured physical case.
Until then, AirTrajectory is an increasingly credible implementation,
not yet a proven external infrastructure dependency.
