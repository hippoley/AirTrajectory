# Execution Evidence Reference for GEISA Community

This document is a proposed Community-project intake note. It is exploratory and
is not an official GEISA artifact.

## Relationship to GEISA

AirTrajectory contains a reference implementation for representing and
verifying execution evidence at the boundary between software intent and
physical or remote infrastructure.

The work is relevant to current GEISA discussions around field-tool behavior,
acknowledgement, execution logging, and conformance reporting. It focuses on
machine-readable distinctions such as:

- test-harness execution status versus target conformance result;
- PASS / FAIL / BLOCKED / UNCERTAIN / NOT_EVALUATED;
- command acknowledgement versus measured observation;
- explicit recovery obligations after uncertain remote or physical execution;
- independent verification before a PASS claim.

The intent is to provide implementation evidence and reusable examples for
GEISA-related experimentation. It does not define GEISA requirements and does
not claim GEISA conformance.

## Project Information

- **Status:** Experimental
- **Maintainer:** Brook / `@hippoley`
- **License:** See the AirTrajectory repository license
- **GEISA versions tested or supported:** None yet. No GEISA runtime or
  conformance-version compatibility is currently claimed.
- **Support:** Best-effort

## Current Reference Artifacts

The current reference implementation includes:

- `schemas/field-execution-record-v0.1.schema.json`
- `schemas/execution-evidence-envelope-v0.1.schema.json`
- `airtrajectory/conformance_record.py`
- `airtrajectory/execution_evidence.py`
- `examples/export_field_execution_record.py`
- semantic regression tests covering PASS, BLOCKED, UNCERTAIN,
  NOT_EVALUATED, recovery, independent verification, and harness/result
  separation
- `docs/geisa-field-tool-conformance-note.md`
- `docs/execution-evidence-geisa-margo-crosswalk.md`

## Building or Using the Project

Install AirTrajectory in editable mode:

```bash
python -m pip install -e .
```

Run the regression suite:

```bash
python -m unittest discover -s tests -v
```

Export one persisted physical-cycle evidence bundle into the reference field
execution record:

```bash
python examples/export_field_execution_record.py \
  --cycle-summary artifacts/verified-replanned-physical-cycle.json \
  --step-summary artifacts/replanned-physical-step.json \
  --verification-receipt artifacts/replanned-physical-cycle-verification.json \
  --out artifacts/field-execution-record.json
```

The domain-neutral `ExecutionEvidenceEnvelope` is derived downstream from
domain-native evidence. It is not intended to replace GEISA's conformance
runner or reporting transport.

## Known Limitations

- No GEISA conformance claim has been made or tested.
- No GEISA specification version is currently declared supported.
- The physical-control reference path has extensive software and real-CONTAM
  verification, but no live CWDS-CA01 field campaign has yet been completed.
- The reference model does not provide distributed consensus or globally
  exactly-once execution across independent gateways.
- The reference model does not define a digital-signature or PKI profile.
- Evidence-set completeness for aggregate signed reports remains an open
  research question and is intentionally not standardized here.
- The generic envelope is exploratory and may change based on external review.

## Proposed Community Location

A natural location, subject to GEISA maintainer guidance, would be under
`tools/`, `example-implementations/`, or `implementation-guidance/`.

The preferred initial contribution should remain small: documentation,
schemas, minimal reference adapter code, and regression fixtures. AirTrajectory
itself can remain maintained in its upstream repository unless GEISA reviewers
prefer vendoring a smaller standalone reference into the Community repository.

## Maintenance Expectations

The project is maintained on a best-effort basis by `@hippoley`.

Any future GEISA Community inclusion should preserve a clear evidence boundary:

- Community inclusion is not GEISA endorsement;
- reference implementation behavior is not normative specification language;
- compatibility or conformance must be demonstrated separately.
