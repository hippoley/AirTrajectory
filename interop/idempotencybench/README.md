# IdempotencyBench interop probe: stale readback after commit

Target upstream: `gssanjana4/idempotencybench`.

This fixture is intentionally written in **IdempotencyBench-native terms**. It
does not require AirTrajectory code or schemas.

## Gap isolated

IdempotencyBench already models:

```text
effect commits
→ caller sees timeout
→ careful agent calls list_effects
→ immediate ledger readback reveals effect
→ no duplicate retry
```

That is an excellent exactly-once baseline. The current `list_effects` channel
is also a perfect/current oracle.

The extension asks what happens when the effect committed but the verification
channel lags:

```text
effect commits
→ caller sees timeout
→ first readback is stale and says "no effect"
→ careful agent retries
→ duplicate side effect
```

This is not `timeout_before_commit`: the effect really committed. Only the
readback view is stale.

## Native regression

Copy `test_stale_readback_regression.py` into the IdempotencyBench repository
root and run:

```bash
python3 test_stale_readback_regression.py
```

Expected results:

- careful agent + no substrate mitigation → **1 duplicate violation**;
- careful agent + runtime receipts → **0 duplicate violations**;
- stable key + idempotency-key mitigation → **0 duplicate violations**.

## Why it matters

The regression separates:

```text
"check before retry"
from
"the check is fresh and authoritative enough to justify retry"
```

The first is agent behavior. The second is an execution-substrate property.

## AirTrajectory relation

This fixture is the external-native translation of AirTrajectory's
`stale-readback` playable probe and
`physical-effect-reconciliation-v0.1.json`.

The shared invariant is:

> matching/readable state is not sufficient evidence if the observation can be
> stale relative to the effect being resolved.

## Evidence boundary

This file has **not** been adopted by IdempotencyBench and is not an upstream
result. The current GitHub integration cannot create an issue in that
repository, so this directory is a ready-to-submit native fixture, not evidence
of maintainer review.
