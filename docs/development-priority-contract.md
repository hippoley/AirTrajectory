# Development Priority Contract

This file defines what should move AirTrajectory forward first.

## P0 — Arbitrary topology intake

Goal: a new floor plan with different room/door/window counts enters the same
pipeline without core code changes.

Evidence required:

- canonical topology emitted from a previously unseen layout;
- user correction path for recognition mistakes;
- variable-size openings and connectivity;
- same topology feeds both trajectory and physics compilation.

## P1 — Multi-environment state and objective

Goal: move beyond CO₂-only control.

Initial engineering target:

- CO₂;
- PM2.5;
- temperature;
- humidity.

TVOC and HCHO become promotion candidates only when emission/source assumptions
are explicit and testable.

Evidence required:

- one shared environmental-state contract;
- one candidate comparison containing all active objectives;
- explicit HOLD option;
- no scalar reward as the only published outcome.

## P2 — Topology-aware joint control

Goal: strategies emerge from topology-derived paths, not fixed window IDs.

Evidence required:

- HOLD baseline;
- Independent per-window baseline;
- deterministic Joint baseline;
- learned/optimized candidate when available;
- same-origin comparison.

## P3 — Physical closed loop

Goal:

```text
measured origin
→ planned action
→ real execution
→ actuator readback
→ fresh environment readback
→ next physical origin
→ replan
```

Until captured on hardware, field validation remains incomplete.

## P4 — Generalization proof

Goal: evaluate on topology families excluded from training.

Evidence required:

- topology-family holdout;
- no exact replay explanation;
- safety non-regression;
- meaningful environmental improvement vs HOLD / Independent;
- report per-metric outcomes, not only aggregate reward.

## P5 — Infrastructure adoption

Only after P0–P4 have reusable contracts should we optimize for third-party
reuse.

Preferred durable artifacts:

- Topology Contract;
- Environmental State Contract;
- Trajectory Contract;
- Physics Adapter Contract;
- Policy Benchmark Contract;
- Physical Adapter Contract.

The first strong ecosystem signal is an independent project keeping one of
these contracts/tests/adapters in its own long-term workflow.

## Deprioritization rule

Do not expand a correctness/evidence/interop feature merely because it is
interesting.

Promote it only when it:

1. removes a blocker on P0–P4;
2. creates a reusable contract another system can consume; or
3. produces independent external pressure / adoption.

This prevents AirTrajectory from drifting into a generic agent-correctness
project.
