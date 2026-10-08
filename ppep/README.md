# PPEP v0.1 — Play Probe Evidence Protocol

**Status:** exploratory working protocol; not a standard.

PPEP answers one narrow question:

> How can one observable action inside a playable experiment be packaged so
> another system can replay, audit, compare, or reject the evidence without
> trusting the project author's narrative?

## Non-goals

PPEP is **not**:

- another analytics platform;
- a replacement for PostHog, experimentation statistics, or session replay;
- a claim that behavior equals preference;
- a claim that browser interaction proves a real-world outcome.

## Minimal record

One v0.1 record binds:

```text
experiment assignment
+ observable interaction
+ before/after state hashes
+ outcome claim
+ evidence references
+ consent/source provenance
+ deterministic evidence hash
```

The most important rule is:

> `outcome.verified = false` is a first-class valid state.

Missing real-world evidence must not be silently converted into success.

## Evidence ladder

PPEP deliberately separates:

```text
observed interaction
→ claimed outcome
→ referenced evidence
→ verified outcome
```

A user clicking, replaying, or modifying something is behavioral evidence. It
is not automatically evidence that a physical or commercial outcome occurred.

## Current use

AirTrajectory's playable correctness probes are the first producer.

The protocol is intentionally model-agnostic so a second producer can later be
a preference-correction experiment, discovery-loop experiment, or another
interactive system without importing AirTrajectory runtime semantics.

## Promotion gate

Do not call PPEP reusable until:

1. one current AirTrajectory web probe emits valid PPEP;
2. a second semantically different probe emits the same core structure;
3. one non-AirTrajectory scenario can use it without changing the core fields;
4. an independent reviewer can validate/tamper-detect a record.

Until then, PPEP remains a v0.1 experiment.
