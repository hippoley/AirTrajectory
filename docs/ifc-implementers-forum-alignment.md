# IFC Implementers Forum interoperability note

AirTrajectory does not define its own community-certification process.

The buildingSMART IFC Implementers Forum already uses focused reference tests
with:

- a reference IFC file;
- a README with concepts and verification checklist;
- optional `success-records/` contributed by tools.

AirTrajectory therefore treats its control-readiness JSON as the machine
record and can render an **IF-style success record** for human review.

This does not imply that AirTrajectory is certified, endorsed, or already
accepted into the IFC Implementers Forum repository.

## Mapping

```text
IF reference IFC
      ↓
AirTrajectory control-readiness inspector
      ↓
machine JSON receipt
      ↓
IF-style Markdown record
```

The formatter lives at:

`airtrajectory/interop/ifc_if_success_record.py`

The intent is to remove format friction before any upstream contribution.
Only a test with a genuinely relevant verification checklist should be
submitted upstream.
