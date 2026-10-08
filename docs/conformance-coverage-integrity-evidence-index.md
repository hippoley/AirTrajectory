# Conformance Coverage Integrity — Evidence Index

This page is a durable verification index for the AirTrajectory work on
conformance-evidence coverage semantics.

It is intentionally narrower than a project narrative. The purpose is to let a
future reviewer verify, in one place, what was actually implemented, what was
proved by executable tests, what external systems independently converged on
similar problems, and what external recognition has or has not yet happened.

## Core implementation trail

| PR | Result | Durable point | Merge commit |
|---|---|---|---|
| #152 | merged | Harness failure must not become target conformance failure | `9a6e6de9227feab77111d9f678cfd90f945324d3` |
| #154 | merged | Conformance claims bind explicit execution-evidence membership | `fd8b40e4f8ff62d58da2df25f3111f8a3b13e1fc` |
| #155 | merged | Membership integrity is not claim completeness | `0a2422be75d505383703c7d70dd9fcd994a89c99` |
| #156 | merged | Expected executions must reconcile against observed evidence | `44d6d96355e3f2364378f773b2c18efd9cb8b7e1` |
| #157 | merged | Expected requirements need explicit claim outcomes | `c1026a6db9afce62a408eaa5d4cdc727b3366d6b` |
| #158 | merged | Coverage invariants packaged as portable adversarial vectors | `eaec55f176df167190cfe2af938044c855df3f91` |
| #161 | merged | Expected execution obligations are bound to stated source identity/revision before coverage reconciliation | `45be2b20a0fdd76cf6ca56dbd1313467851ccd1d` |
| #166 | merged | Veklom omission question resolved through VCGB expected-population + EEE per-execution layering | `df1468a7aae1efdc019157e8a295f28b3de7e9df` |
| #167 | merged | Emilia coverage question resolved through CAP-1 examined-set layering without overclaiming source-population completeness | `ccbd747e69fad35fca85f6356f1be2ce876fdfa9` |
| #168 | merged | Sanitized physical-effect lost-ACK/readback/compensation reference scenario for OpenTelemetry discussion | `bf8af38a29be4f53749117899caaf8d4efa51091` |

## Portable verification artifact

The smallest reusable artifact is:

`test-vectors/conformance-coverage-v0.1.json`

The current vectors freeze these distinctions:

```text
valid included evidence != complete evidence coverage

MISSING != NOT_EVALUATED

NOT_SATISFIED != MISSING

positive traceability != requirement-claim completeness
```

The vectors are replayed in:

`tests/test_conformance_coverage_vectors.py`

A future implementation can use a different schema, signature mechanism,
registry, profile model, or outcome vocabulary and still test these invariants.

## External reality anchors

The work was refined against independently developed external systems rather
than treated as a self-contained architecture.

### Margo

Margo's conformance direction publicly contains:

- CR-IDs as stable conformance requirement identifiers;
- a Spec Traceability Matrix mapping requirements to tests/assertions;
- a Conformance Test Toolkit;
- signed conformance results;
- a Public Conformance Registry.

These are external problem anchors for requirement and execution coverage.
AirTrajectory does not claim authorship of those structures.

### Veklom EEE-Core

Veklom independently developed EEE-Core before AirTrajectory's #154–#158
sequence. EEE-Core addresses signed execution evidence, offline verification,
gate coverage, fail-open handling, and omission attacks.

This independent chronology is important: it is evidence of problem
convergence, not evidence that Veklom adopted AirTrajectory.

On 2026-10-08, an external collision was opened in Veklom:

- `reprewindai-dev/veklom-FRONTEND#146`
- question: whether EEE can detect omission relative to a precommitted expected
  execution obligation
- portable AirTrajectory vectors linked directly in the issue

The issue was later closed by its author after Veklom's published VCGB design resolved the layering question: VCGB binds the expected scenario/run population, while EEE remains the per-execution evidence-integrity layer. This is a scope resolution from external project documentation, not maintainer endorsement.

### Emilia Protocol / Action Evidence Boundary

Emilia Protocol independently carries an explicit formal/security invariant named
`CoverageDoesNotProveCompleteness`. Its Action Evidence Boundary work also
requires hostile omission/substitution vectors, and its bounded-execution work
separates outside-plan claims from population-completeness assumptions.

This is a stronger external convergence signal than a loose terminology match:
AirTrajectory and Emilia independently encode the same semantic boundary in
executable/formal verification work.

On 2026-10-08, a second external collision was opened:

- `emiliaprotocol/emilia-protocol#914`
- purpose: ask whether AirTrajectory's schema-neutral coverage vectors can be
  mapped into Emilia's existing hostile/conformance vector format
- no adoption or endorsement is implied until an external maintainer responds,
  cites, reuses, or requests a concrete mapping

## Recognition status

As of 2026-10-08:

```text
third-party dependency on AirTrajectory vectors   NOT YET OBSERVED
third-party citation of AirTrajectory              NOT YET OBSERVED
third-party maintainer endorsement                  NOT YET OBSERVED
external public collisions                          YES (#146 resolved, #914 open)
independent problem convergence                     YES
portable executable evidence                        YES
```

Opening an external issue is not counted as external recognition. This index
must only be upgraded when an external party responds, cites, reuses, adapts,
or requests further review.

## Identity value

The durable technical contribution is not a claim to own a conformance standard.
It is a reproducible body of work around one boundary:

```text
what should have been covered
        ↕
what was actually executed
        ↕
what evidence exists
        ↕
what the final claim says
```

The identity claim supported by the evidence is therefore:

**Conformance Coverage Integrity contributor**

not:

- certification authority;
- Margo architect;
- EEE author;
- formal standards maintainer.

Those stronger identities require external governance or adoption evidence.

## Upgrade conditions

This evidence index should only be upgraded from "portable proof" to "external
recognition" when at least one of the following happens:

1. an external maintainer replies substantively to #146, #914, or an equivalent
   verifier discussion;
2. another repository reuses/adapts a coverage vector;
3. another issue/PR cites this repository or a specific invariant;
4. a verifier adds a regression test derived from one of these cases;
5. an external maintainer requests review of coverage/evidence semantics.

Those events are the transition from artifact accumulation to portable
reputation.

## Current external-discussion position

A third external discussion surface now exists in
`open-telemetry/semantic-conventions-genai#462`, where the repository linked a
sanitized physical-effect scenario distilled from the AirTrajectory execution
boundary. The surrounding thread independently discusses mutating effects,
unresolved effects, retries, compensation, and causal/effect semantics.

As of 2026-10-08, this is **active participation in a third-party technical
discussion**, not evidence that OpenTelemetry adopted AirTrajectory's model.
No maintainer has yet replied directly to the AirTrajectory fixture or cited it
as a normative/reference artifact.

This distinction remains important:

```text
external discussion participation        YES
direct third-party reply to our artifact  NOT YET OBSERVED
third-party reuse/adoption                 NOT YET OBSERVED
```

The strongest durable result of the current round is therefore the combination
of merged executable invariants, portable adversarial vectors, resolved
cross-project layering comparisons, and a sanitized external-effect reference
scenario—not a claim of upstream adoption.
