# Playable Correctness Probes

This directory is the public entry point for **third-party-verifiable units** in AirTrajectory.

The repository historically organizes artifacts by type:

```text
airtrajectory/   runtime implementation
test-vectors/    machine-readable adversarial cases
interop/         external cross-project mappings
docs/            explanations / evidence indexes
web/             playable presentation
```

That is good for maintainers but expensive for a first-time reviewer. `probes/`
adds a thin evidence spine without moving or renaming those durable paths.

Each probe must connect all of these:

```text
Observed Phenomenon
→ Behavioral Mechanism
→ Probe Primitive
→ Digital Translation
→ Measurable Behavior
→ Reality Evidence
→ Build / Double / Kill
```

and, when a runtime invariant exists:

```text
playable interaction
→ machine vector
→ executable implementation
→ field / external evidence
→ external reuse or challenge
```

## Long-term retrieval principle

**Human-behavior-first, not technology-first.**

The probe layer should learn from any mechanism that makes people voluntarily
approach, touch, continue, replay, explore, modify, share, collect, wait, or
return — regardless of whether the source is AI, HCI, retail, games, packaging,
museums, LiveOps, menus, theme parks, queues, drops, feeds, or physical spaces.

The goal is not to copy consumer-engagement tricks. The goal is to make hard
correctness claims *voluntarily inspectable* and to collect stronger evidence
than “someone viewed the page”.

## Core behavioral signals

Prefer:

- Voluntary Continuation Rate
- Exploration Depth
- Return Without Prompt
- Glance → Touch
- First → Second Probe
- Surprise → Replay
- Discovery → Share

over raw page views or likes.

## Evidence boundary

A browser probe is not physical evidence.

A probe can be:

- `browser-explanation`
- `machine-vector`
- `runtime-enforced`
- `field-observed`
- `independently-reproduced`

Those levels must never be collapsed.

## Current catalog

See `catalog.v0.1.json`.

The current three probes deliberately cover different failure semantics:

1. **rain-after-approval** — authorization freshness / TOCTOU;
2. **lost-ack** — logical effect vs transport attempt;
3. **stale-readback** — fresh measured evidence vs plausible stale value.

## Promotion rule

A new probe should enter this directory only when it has at least:

1. one concrete failure a real system could make;
2. one observable user action;
3. one machine-checkable invariant or explicit nonclaim;
4. one Reality Evidence path;
5. a clear Build / Double / Kill threshold.

Do not add a probe merely because an LLM can generate an interesting scenario.

## Strategic goal

The target is not “a nicer demo”.

The target is a reusable **reference probe corpus for agent external-effect
correctness**: small scenarios that another runtime, reviewer, standards group,
or physical system can independently reproduce, reject, adapt, or depend on.

That is the point where AirTrajectory can move from self-published proof of work
toward externally useful proof of position.
