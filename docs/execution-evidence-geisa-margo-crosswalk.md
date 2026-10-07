# Execution evidence crosswalk: GEISA and Margo

> Exploratory, non-normative, and not an official artifact of either project.

## Why this crosswalk exists

Two independent infrastructure ecosystems are now exposing adjacent gaps:

- GEISA is discussing field-tool behavior, acknowledgement, execution logging,
  and report/schema structure.
- Margo is building a conformance framework with persona-specific test suites,
  signed reports, telemetry/evidence capture, and reusable test-case schemas.

The overlap is not "use the same test runner." The overlap is the semantic
question underneath both systems:

> What exactly happened during one execution, what target did it affect, what
> was observed afterward, and can another verifier distinguish PASS from FAIL,
> BLOCKED, or an uncertain outcome?

AirTrajectory's existing FieldExecutionRecord is one physical-control profile
of that problem. It should not become the generic model by accident.

## Minimal shared core

The exploratory `ExecutionEvidenceEnvelope v0.1` therefore keeps only fields
that remain meaningful across a physical actuator transition, an industrial
edge conformance test, or another infrastructure operation:

- execution identity and parent lineage;
- subject identity/version;
- target identity and execution scope;
- operation identity, request identity, acknowledgement identity;
- whether mutation is expected;
- observations;
- PASS / FAIL / BLOCKED / UNCERTAIN;
- recovery requirement and outcome;
- independent verification state;
- provenance and artifact references;
- explicit evidence boundary;
- opaque domain extensions.

Physical details such as opening ID, zone ID, measured window position, CO2, or
rain remain profile extensions rather than core semantics.

## GEISA mapping

Current open discussions include:

- `geisa/specification#110` — field tool behaviors
- `geisa/specification#113` — acknowledgement / credit for messages
- `geisa/conformance#21` — execution logging
- `geisa/conformance#37` — XML report schema

The envelope is compatible with the existing proposal to keep JUnit XML as the
test-runner/reporting transport while attaching a semantic sidecar.

Potentially reusable core semantics:

- acknowledgement is distinct from observation;
- target identity remains stable across the operation;
- replay/uncertain outcomes are not represented as ordinary PASS;
- recovery creates new evidence instead of silently reusing stale intent;
- a final PASS requires explicit verification evidence.

## Margo mapping

Current public conformance work includes:

- `margo/sandbox#243` — conformance framework and signed statement of
  conformance, including optional OTEL traces/telemetry as evidence;
- `margo/sandbox#277` — test-case writer/generator and JSON Schema validation;
- `margo/sandbox#278` — persona-specific conformance execution and signed
  shareable reports.

The envelope is not intended to replace those tools or their report format.
Instead, it can sit one layer below a signed report:

```text
test case
  ↓
runner / fixture
  ↓
ExecutionEvidenceEnvelope(s)
  ↓
suite aggregation
  ↓
signed conformance report
```

A signed PDF or summary can then attest to a set of machine-readable execution
records instead of being the only durable representation of what occurred.

## Why UNCERTAIN matters

PASS/FAIL is insufficient for operations that may mutate physical or remote
state.

Example:

```text
request sent
→ remote target may have acted
→ transport disappears before response
```

The correct evidence state is not automatically FAIL and must never be inferred
as PASS. It is UNCERTAIN, and it creates a recovery obligation.

That distinction is especially important when a later signed conformance report
is expected to mean more than "the test runner exited zero."

## Evidence layering

The intended layering is:

```text
domain-native evidence
        ↓
domain profile
  (FieldExecutionRecord)
        ↓
ExecutionEvidenceEnvelope
        ↓
JUnit / JSON / OTEL correlation / report aggregation
        ↓
signed conformance statement
```

Each layer loses detail. A higher layer must not claim authenticity or certainty
that the lower evidence does not establish.

## Current status

AirTrajectory currently implements:

- `schemas/field-execution-record-v0.1.schema.json`
- `airtrajectory/conformance_record.py`
- `schemas/execution-evidence-envelope-v0.1.schema.json`
- `airtrajectory/execution_evidence.py`

The implementation is reference evidence only. It is not a GEISA or Margo
schema, compliance claim, or proposed standard at this stage.

The purpose of this crosswalk is to test whether the same semantic primitive is
actually useful in two independent infrastructure ecosystems before proposing
it upstream.
