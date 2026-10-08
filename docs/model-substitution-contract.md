# Model Substitution Contract

AirTrajectory treats model intelligence as replaceable and evidence authority as
non-replaceable.

This is an explicit anti-commoditization boundary.

## Contract

A planner may be replaced by:

- a stronger LLM;
- a smaller local model;
- a classical controller;
- an RL policy;
- a human operator;
- a future agent architecture.

That substitution may change the proposed action.

It must **not** change the truth value of evidence that already exists.

```text
better model
!=
better evidence
```

More specifically:

```text
model confidence
!= physical measurement

model narrative
!= missing execution

model explanation
!= requirement coverage

transport ACK
!= physical effect

simulated trajectory
!= physical tau0
```

## Why this matters

If a future foundation model can replace AirTrajectory's planner and thereby
erase the value of the repository, then the durable contribution was never the
planner.

The durable layer is the boundary between:

```text
proposal
execution
measurement
evidence
coverage
claim
```

Those boundaries survive model substitution because they are anchored in:

- externally committed expected populations;
- deterministic verifier semantics;
- independently measurable physical state;
- explicit evidence classes;
- cross-system interoperability constraints.

## Machine-readable vectors

`test-vectors/model-substitution-independence-v0.1.json`

The vector set checks four cases:

1. the same complete evidence set yields the same coverage verdict under
   different model identities and narratives;
2. a stronger model cannot explain away a missing expected execution;
3. requirement coverage remains structural even when a model supplies persuasive
   narrative;
4. a model assertion cannot promote the deterministic mock fallback from
   `tau_sim` into physical or engineering evidence.

The corresponding regression test is:

`tests/test_model_substitution_contract.py`

## Product implication

Models compete on proposing better actions.

AirTrajectory's long-lived value should accumulate in the harder-to-substitute
layers:

- physical-system integration;
- authoritative readback;
- execution identity and idempotency;
- evidence and coverage reconciliation;
- standards-compatible reference scenarios;
- replayable field evidence;
- real sim-to-field validation.

That is also the innovation gate for future work: a feature that only improves
prompting or one model's planning quality is not enough by itself. A feature
should preferably strengthen a physical, evidentiary, interoperability, or
measured-performance boundary.
