# Execution coverage reconciliation

This module is intentionally smaller than a conformance-plan schema.

External reality in Margo's conformance work already includes:

- selecting persona-specific test suites and predefined groupings;
- adding validated test cases to a selected suite;
- executing the selected test suites;
- producing signed reports and evidence.

That is enough to establish the semantic need for an **expected execution set**,
but not enough to justify inventing Margo's authoritative plan format locally.

AirTrajectory therefore accepts the expected execution IDs from an external
source of truth and only answers the coverage question:

```text
expected execution obligation
          ↕
coverage reconciliation
          ↕
observed execution evidence
```

The result distinguishes:

- `COMPLETE`: every expected execution has evidence and no extra execution appeared;
- `MISSING`: at least one expected execution has no evidence record;
- `UNEXPECTED`: all expected executions are present, but extra execution evidence exists.

`MISSING` is intentionally different from `NOT_EVALUATED`:

- `MISSING` means no execution evidence exists for an execution that should have existed.
- `NOT_EVALUATED` means an execution evidence record exists, but target evaluation did not complete.

No signing, plan schema, or Margo-specific identifier format is introduced here.
Those remain external-contract decisions.
