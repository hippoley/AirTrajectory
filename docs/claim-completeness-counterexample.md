# Claim-completeness counterexample

## Why this exists

Margo sandbox issue #328 sketches a signed-conformance chain around a rendered
PDF, embedded evidence, X.509 signing, RFC3161 timestamping, and a second
certificate file that carries the report SHA-256.

That is useful for document authenticity and tamper detection, but it exposes a
separate question:

> How does a verifier know that the signed report covers every execution that
> was supposed to be part of the selected conformance run?

AirTrajectory's `ExecutionEvidenceSet v0.1` freezes the membership it is given.
It does **not** yet prove that the producer supplied the complete expected
membership.

## Minimal counterexample

Assume the selected suite is expected to execute:

```text
exec-a  PASS
exec-b  FAIL
```

A complete evidence set correctly aggregates to:

```text
FAIL
```

But if `exec-b` is removed *before* the evidence set is built, the remaining
manifest is still internally valid and aggregates to:

```text
PASS
```

Its digest is different, but a verifier cannot call that digest "wrong" unless
the verifier also has an independently committed statement of which executions
were expected.

The executable counterexample is:

```text
tests/test_claim_completeness_counterexample.py
```

## Boundary clarified

This separates two properties:

```text
membership integrity
    = the records inside this manifest cannot be changed unnoticed

claim completeness
    = the manifest contains every execution the run was obligated to cover
```

The first is implemented by `ExecutionEvidenceSet v0.1`.

The second still requires an external commitment, such as a deterministic test
plan / expected-execution manifest whose identity is itself bound into the
signed claim.

## Why not implement that layer yet

This repository deliberately stops at the counterexample for now.

Margo #278/#297/#298/#328 are concrete external implementations of the signed
conformance-report problem. Before inventing another schema locally, the useful
next reality check is to see what object Margo treats as the authoritative
selected test plan and whether its verifier is expected to prove coverage
against it.

That external contract should drive the smallest next implementation.
