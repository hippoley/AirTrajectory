# Requirement-claim coverage reconciliation

Margo's conformance documentation introduces three important external objects:

- authoritative CR-IDs;
- a Spec Traceability Matrix (STM) mapping requirements to test cases and expected assertions;
- a signed Conformance Result submitted to a Public Conformance Registry.

The current draft Conformance Result includes a list of
`requirements_satisfied`. That is useful for positive traceability, but absence
from a satisfied-only list is ambiguous:

```text
CR-ID absent
  = requirement not satisfied?
  = requirement not evaluated?
  = requirement skipped?
  = report generator omitted it?
```

A verifier cannot prove claim completeness from a positive-only set.

This module therefore models only the smallest reusable invariant:

> Every CR-ID in the externally resolved profile/STM obligation must have an
> explicit requirement-claim outcome.

The caller supplies:

- the expected CR-ID set from the external profile/STM;
- reported requirement claims, each with `cr_id` and a non-empty `outcome`.

AirTrajectory does **not** define the outcome vocabulary here. Margo may choose
different normative states. The module only distinguishes coverage:

- `COMPLETE`: every expected CR-ID has an explicit claim entry;
- `MISSING`: one or more expected CR-IDs have no claim entry;
- `UNEXPECTED`: all expected CR-IDs are covered, but extra CR-IDs are claimed.

This preserves an important distinction:

```text
NOT_SATISFIED != MISSING
```

An explicitly failed or unsatisfied requirement is still covered by the claim.
A missing requirement has no explicit claim semantics at all.

External reality anchors:

- `margo/conformance_documentation/docs/conformance_test_toolkit/ctt_overview.md`
- `margo/conformance_documentation/docs/conformance_test_toolkit/conformance_artifacts.md`
- `margo/conformance_documentation/docs/conformance_test_toolkit/crid-specification.md`
