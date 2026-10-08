# Authorization → Effect Correctness Frontier

This page is a durable evidence map for one narrow research/engineering question:

> When an agent is authorized to cause an external effect, what must remain true
> from authorization through dispatch, physical outcome, compensation, and audit?

It is **not** a claim that AirTrajectory defines a standard or originated this
problem space. The purpose is to make the current implementation boundary,
external prior work, and remaining gaps reviewable from one place.

## External convergence

Several independent 2026 lines now converge on adjacent parts of the same
boundary:

- **Authorization-Execution Gap** (arXiv:2605.11003): one-shot authorization is
  insufficient when authority can diverge during execution.
- **Approved Too Late / Verdict Staleness** (arXiv:2608.26306): an approval may
  be correct at check time but stale by actuation; use-time freshness is a
  measurable property.
- **Authorization Revocation for Long-Running AI Agents**
  (arXiv:2609.21284): cancellation or credential revocation does not by itself
  prove that delegated/asynchronous old-root effects have quiesced.
- **OpenTelemetry GenAI durable runtime discussion #462**: durable execution,
  retries, mutable external effects, compensation, and causal identity need
  interoperable observability semantics.
- **HALO E003 verdict-freshness experiment**: independently reproduces the
  stale-verdict boundary and uses perfect use-time revalidation as a synthetic
  oracle control.

These are problem-space signals, not adoption of AirTrajectory.

## AirTrajectory: implemented boundary

The current repository has executable evidence for the following distinctions:

| Boundary | Executable evidence |
| --- | --- |
| logical effect != transport attempt | #170 |
| transport/ACK evidence != physical effect outcome | #172 |
| compensation success != original history erasure | #173 |
| authorization valid at check time != valid at dispatch | #175 |
| HALO synthetic oracle != physical measured revalidation | #178 |
| evidence-set integrity != claim completeness | #155/#156 |
| expected obligations must bind stated source provenance | #161 |

The physical execution path now contains a fail-closed use-time gate:

```text
measured physical origin
→ bounded authorization
→ freshness/readiness checks
→ durable execution lease
→ fresh measured pre-dispatch position + rain revalidation
→ physical dispatch
→ ACK
→ measured post-action readback
→ effect reconciliation
→ verified compensation if required
→ fresh next-origin evidence
```

## Current durable invariants

```text
valid authorization at T1
!=
valid authorization at T2

transport success
!=
effect success

retry attempt
!=
logical effect

compensation success
!=
original effect never happened

fresh-looking value
!=
fresh attributable evidence
```

These invariants are intentionally model-agnostic. A stronger LLM can propose
better actions, but it does not eliminate the need to know whether the world
changed, whether authority was still valid, or whether an external effect
actually occurred.

## Why this is harder to commoditize with better models

The correctness boundary depends on facts outside the model:

- current hardware/target identity;
- measured physical state;
- observation freshness;
- authorization state at use time;
- retry/idempotency history;
- effect outcome and uncertainty;
- compensation outcome;
- provenance and replayable evidence.

Models can help generate code, policies, or hypotheses, but they cannot replace
the authoritative observation or enforcement point that determines those
facts.

## What is not yet proven

AirTrajectory does **not** currently prove:

- third-party adoption of these semantics;
- compatibility with OpenTelemetry, HALO, or the cited research systems;
- root-scoped revocation/quiescence across delegated asynchronous work;
- distributed consensus over authorization state;
- global rollback or global physical-state correctness.

The next frontier should be promoted only when a real consumer exposes it.

## Most important adjacent frontier: revocation after delegation

The strongest newly emerging adjacent problem is no longer only freshness.

Long-running agents may enqueue, delegate, retry, or externalize work before an
authorization is revoked. A later revocation can therefore be true while an
old authorized effect is still capable of materializing.

AirTrajectory should **not** invent a generic revocation protocol yet. The
promotion criterion is a real execution path with at least one of:

- queued physical command;
- delegated actuator/tool execution;
- asynchronous callback;
- provider-side operation;
- independently authorized shared work.

Only then should a revocation/quiescence primitive move from frontier note to
runtime contract.

## External validation ladder

The project should treat these as distinct evidence levels:

```text
independent problem convergence
→ third-party discussion
→ direct reply/challenge
→ vector reproduction
→ external implementation
→ compatibility obligation
→ stewardship / governance role
```

As of 2026-10-08, AirTrajectory has reached independent convergence and active
third-party discussion surfaces, but not external reuse or compatibility
obligation.

## Review links

- AirTrajectory #175 — physical authorization-use freshness gate
- AirTrajectory #178 — HALO E003 physical freshness crosswalk
- HALO issue #22 — physical extension question for observation-bounded
  use-time revalidation
- OpenTelemetry GenAI #462 — durable runtime / external-effect semantics

The value of this page is not the vocabulary. It is the public chain from
external problem → executable counterexample → fail-closed runtime rule →
portable review artifact.
