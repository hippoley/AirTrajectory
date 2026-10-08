# OpenTelemetry physical-effect reference scenario

This artifact is the concrete follow-through to the physical-control example
shared in `open-telemetry/semantic-conventions-genai#462`.

The scenario is intentionally implementation-neutral and sanitized:

```text
mutating effect intent
→ dispatch
→ ACK lost
→ physical outcome remains unresolved
→ authoritative actuator readback
→ bounded compensation
→ compensation readback
→ fresh measured post-state
```

The purpose is to test whether generic agent/external-effect observability can
preserve several distinctions without introducing physical-device-specific
semantic conventions.

## Required distinctions

- **effect intent vs effect outcome**
- **logical effect identity vs attempt/retry identity**
- **transport evidence vs authoritative effect evidence**
- **transport failure vs unresolved effect**
- **compensation requested vs compensation verified**
- **fresh measured state vs stale pre-action state**

The machine-readable scenario is:

`interop/opentelemetry/physical-effect-lost-ack-v0.1.json`

## Why this is useful

A lost transport ACK cannot tell an operator whether a physical mutation:

- never happened;
- happened completely;
- happened partially;
- happened and then drifted.

Blind replay can therefore create a second mutation.

The reference scenario forces observability to retain the unresolved state until
an authoritative readback or reconciliation result exists. Compensation is a
separate action with its own attempt identity and must not be reported as
successful until independently verified.

## Boundary

This is **not** a proposal for final OpenTelemetry field names.

It is a reference case that can be used to evaluate candidate semantics for
state transitions, external effects, retries, reconciliation, and compensation.
