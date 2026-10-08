# Physical Effect Reconciliation Benchmark

This benchmark turns AirTrajectory's physical-effect reconciliation logic into a
portable production-safety artifact.

It is deliberately not tied to ventilation.

## Problem

For a real external side effect:

```text
dispatch success
!=
effect success
```

A lost acknowledgement, cached state, runtime estimate, or model narrative cannot
prove what happened in the physical world.

The effect may only move out of `UNRESOLVED` when the verifier has fresh,
measured, post-action evidence with an explicit measurement source.

## Vector set

`test-vectors/physical-effect-reconciliation-v0.1.json`

The cases cover:

- fresh measured readback confirms the intended effect;
- fresh measured readback contradicts it;
- stale readback remains unresolved;
- estimated state remains unresolved;
- missing observation remains unresolved;
- measured data without a source remains unresolved.

The vectors replay directly through:

`airtrajectory.physical_effect_reconciliation.reconcile_physical_effect()`

via:

`tests/test_physical_effect_reconciliation_vectors.py`

## Landing value

The same boundary appears in any agent/controller that can cause an external
side effect whose outcome is independently observable:

- robotics;
- industrial automation;
- building control;
- vehicle/actuator control;
- remote infrastructure operations;
- agent tool execution;
- transaction/payment orchestration.

A future model can improve the **proposal**.

It cannot eliminate the need to determine the **effect**.

That makes this artifact both a deployment-safety benchmark and a long-lived
research boundary that does not depend on one model family.
