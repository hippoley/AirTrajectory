# AirTrajectory User Story Gap Audit

Date: 2026-10-08

This audit evaluates the repository against the product user story, not against
repository complexity. A capability is counted only when executable evidence
exists at the matching layer.

## Executive conclusion

AirTrajectory has over-invested in reliability / evidence / interoperability
relative to the product-control loop.

The highest-value missing bridge is:

```text
Environmental State
→ inspectable multi-objective goal
→ candidate-future comparison
→ HOLD / Independent / Joint decision
```

Without that bridge, arbitrary-topology intake improves the input surface but
does not yet deliver the original multi-environment control promise.

## Story-by-story audit

| Story | Status | Current evidence | Missing acceptance evidence |
| --- | --- | --- | --- |
| 1 Import any home | PARTIAL | fixed JSON contract; imported-layout work in PR #195; IFC adapter/readiness work in progress | raster/CAD/SVG importer; interactive room/wall correction; merged public runtime receipt |
| 2 Arbitrary room/door/window counts | STRONG PARTIAL | variable BuildingTopology; non-W1/W2/W3 path discovery; cross-topology runtime tests | broader real imported topology corpus; variable topology through engineering-valid CONTAM compilation |
| 3 Environmental world state | CONTRACT EXISTS | `environmental_state.py`; schema; evidence classes; semantic crosswalk | state consumed by main policy / physics / comparison loop |
| 4 Goals instead of actuator commands | MISSING CORE | docs only; UI has coarse local objective labels | inspectable objective contract over IAQ/comfort/motion/safety |
| 5 Topology-aware joint strategies | PARTIAL | VentilationPath discovery; path-derived candidates; real-CONTAM Golden Case | objective-aware ranking across environmental dimensions; internal-opening strategy beyond current held-door assumption |
| 6 Preview multiple futures | CO2-CENTRIC PARTIAL | counterfactual branches and UI; CO2-oriented frames | shared multi-environment outcome vector and same-origin comparison |
| 7 Conflicting environmental goals | MISSING CORE | documented examples only | executable CO2-vs-PM2.5 / comfort conflict evaluation; HOLD can win |
| 8 Conservative real execution | SOFTWARE-STRONG / FIELD-MISSING | WindowPilot bridge, preflight, readback, leases, reconciliation | real commissioning and captured physical trajectory |
| 9 Replan on world change | STRONG SOFTWARE PARTIAL | stale invalidation, physical-origin replan, bounded next action | real environmental trigger loop across multiple environmental fields |
| 10 Learn from prediction error | PARTIAL | trajectory/dataset/BC/offline-Q infrastructure | calibrated predicted-vs-measured error loop and model update evidence |
| 11 Generalize to unseen topology | PARTIAL | toy benchmark trains 2–4 rooms, tests 5-room chains | held-out topology families (branch/hub/loop/irregular), real physics, multi-environment, sim→real |
| 12 Reproducible benchmark | PARTIAL | unseen-topology benchmark; Golden Case; receipts | unified HOLD/Independent/Joint/learned multi-environment benchmark contract |
| 13 Third-party infrastructure reuse | SHAPE EXISTS / ADOPTION MISSING | topology/environment/readiness schemas; external pressure mapping | independent adopter, upstream test, citation, compatibility obligation |

## Drift audit

### High-value durable assets

- variable-size topology and semantic VentilationPath identity;
- trajectory / physical-origin lineage;
- real CONTAM adapter;
- environmental-state evidence contract;
- WindowPilot physical boundary;
- public-model compatibility pressure.

### Useful but overgrown relative to product value

- generic correctness/evidence expansions not tied to a product blocker;
- additional provenance schemas without an independent consumer;
- interoperability notes that do not produce an upstream test or adapter.

### Weak / misleading surfaces to fix

- web UX still validates `fixed-floorplan` and presents rooms as locked;
- UI comparison remains largely CO2 / hand-authored fallback oriented;
- README capability language can make the system feel closer to arbitrary-layout
  product completion than the user-facing edit/import path actually is;
- unseen-topology benchmark is scale generalization over chain scenarios, not
  broad structural generalization.

## Development valuation rule

A change is promoted when it materially improves at least two of:

1. user-story closure;
2. independent reproducibility;
3. physical evidence;
4. held-out generalization;
5. third-party compatibility/adoption;
6. durable model-independent contract value.

A change that improves only repository sophistication is deprioritized.

## Immediate sequence

### Gate A — Multi-environment decision core

Implement one physics-neutral, inspectable objective/outcome contract for:
CO2, PM2.5, temperature, humidity, actuator movement and safety.

Acceptance:
- HOLD is a first-class candidate;
- every candidate exposes per-metric deltas;
- conflicting objectives remain visible;
- optional scalar ranking cannot replace the vector.

### Gate B — Connect real candidate futures

Feed the objective evaluator from real-CONTAM / fast-backend candidate outcomes
where those fields are physically available. Do not fabricate unavailable
pollutants.

### Gate C — User-goal contract

Translate explicit user preferences into objective bounds/weights. Natural
language parsing is replaceable and not the moat.

### Gate D — Arbitrary-layout correction surface

After PR #195 is stable, update the browser/runtime to accept imported layouts
and support explicit correction operations. Do not keep a fixed-floorplan-only
web validation gate.

### Gate E — Structural generalization benchmark

Split by topology family, not only room count. Add chain/branch/hub/loop
families and exact-replay checks.

### Gate F — Physical multi-environment origin

Capture a real physical origin with at least CO2 + temperature + humidity +
rain/window state, then close measured-origin → action → readback → next-origin.

PM2.5 enters once a trustworthy indoor/outdoor sensor path exists.

### Gate G — External adoption

Only after the above contracts are executable should upstream/community effort
be increased. The desired signal is a third party retaining a schema/test or
requesting compatibility.

## Kill / pivot triggers

Revalue the node if, after a focused adoption window:

- no independent user can run the contract/benchmark;
- openBIM control-readiness produces no upstream interest;
- the integration burden is larger than the control value;
- real field data cannot support meaningful multi-environment claims.

If that happens, preserve durable topology/trajectory/physical-evidence assets
and pivot to the highest-value adjacent node rather than continuing by inertia.
