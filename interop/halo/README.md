# HALO E003 ↔ physical authorization freshness

This note maps HALO's synthetic verdict-freshness experiment to one physical
actuation boundary in AirTrajectory.

The purpose is **comparison, not compatibility or novelty claiming**.

HALO E003 asks how containment degrades when approval is correct at check time
but state changes before use. Its `use_time_revalidation` protocol is a perfect
oracle control by construction. AirTrajectory #175 exercises the same temporal
boundary against physical evidence:

```text
authorization created from measured origin
→ time passes / world may change
→ fresh measured position + rain are re-observed
→ stale or drifted authorization is rejected
→ only then may physical dispatch occur
```

The important extension is that a physical runtime does not have a perfect
oracle. It must decide whether the observation used for revalidation is itself
fresh, measured, attributable, and relevant.

## Review artifact

Machine-readable crosswalk:

`interop/halo/halo-e003-physical-freshness-crosswalk-v0.1.json`

Portable AirTrajectory vector:

`test-vectors/authorization-use-freshness-v0.1.json`

Merged implementation:

AirTrajectory #175 — fail closed when physical authorization is stale at
dispatch.

## Boundary

This artifact does not propose changes to HALO E003 and does not claim that
AirTrajectory implements HALO, Freshness-Bounded Shield, or any formal
authorization-revocation protocol. It isolates a physical-world extension
question:

> What replaces the perfect use-time oracle when authorization guards a
> real external effect and the observation itself can be stale or missing?

That question is intentionally narrow enough to be reproduced by another
runtime without adopting AirTrajectory's schema.
