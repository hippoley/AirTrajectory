# IFC / IDS / AirTrajectory Control-Readiness Boundary

AirTrajectory does **not** define a replacement for buildingSMART IDS.

## Standards boundary

buildingSMART IDS 1.0 is the standards layer for expressing and checking
machine-readable IFC information-delivery requirements.

AirTrajectory's control-readiness layer starts **after** that question:

```text
IFC schema validity
        ↓
IDS information-delivery compliance
        ↓
AirTrajectory control-readiness
        ↓
Layout Contract
        ↓
physics / trajectory / control
```

The layers answer different questions.

### IFC schema validation

"Is this an IFC model that satisfies schema-level rules?"

Use IFC / IfcOpenShell validation.

### IDS

"Did the producer deliver the agreed entities, attributes, quantities,
properties, classifications and supported relations?"

Use buildingSMART IDS.

### AirTrajectory control-readiness

"Can the delivered model be converted into a variable-topology ventilation
control problem without fabricating physical facts?"

This includes requirements that are not fully representable by IDS 1.0,
especially geometry-derived and control-runtime conditions.

## Requirements split

Machine-readable classification:

`interop/ifc/control-requirements-v0.1.json`

### IDS-addressable examples

- presence of `IfcSpace`;
- stable element identity;
- required quantities/attributes when represented in IFC;
- door/window width and height when available as IFC attributes/quantities.

### Runtime / geometry gate examples

- usable 2D/3D projected geometry;
- positive geometry-derived zone volume when not delivered as a quantity;
- one-space vs two-space opening adjacency after resolving actual model
  relationships;
- non-degenerate ventilation path;
- ability to derive a topology accepted by the physics adapter;
- source provenance and importer fidelity.

## Principle

If a requirement belongs in an open standard, AirTrajectory should map to the
open standard rather than inventing a parallel vocabulary.

The project should only own the residual control-specific boundary needed to
turn openBIM information into reproducible physical trajectories.
