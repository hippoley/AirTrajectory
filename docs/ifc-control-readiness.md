# IFC Control Readiness v0.1

AirTrajectory treats IFC as an **open building representation**, not as a guarantee
that a model already contains enough semantics for physical ventilation control.

The control-readiness gate answers:

> Can this IFC-derived building model enter a physics-grounded ventilation
> trajectory without inventing missing engineering facts?

## Why this exists

A file may be syntactically valid IFC while still lacking control-critical
semantics such as:

- usable `IfcSpace` volumes;
- door/window dimensions;
- unambiguous opening-to-space adjacency;
- geometry that can be projected into the topology used by the physics backend.

Those are different questions:

```text
IFC schema validity
        ≠
building simulation readiness
        ≠
ventilation-control readiness
```

AirTrajectory only claims the third when the required evidence is present.

## v0.1 minimum gate

### Space evidence

Each controllable zone requires:

- stable source identity;
- usable projected geometry;
- positive volume.

### Opening evidence

Each door/window used by the controller requires:

- stable source identity;
- positive width and height;
- projected geometry;
- exactly one adjacent modeled space for an exterior opening, or exactly two
  modeled spaces for an internal opening.

### Provenance

An imported Layout Contract binds:

- source format;
- source SHA-256;
- importer identity/version;
- declared geometry fidelity.

## Machine result

The result is either:

```json
{
  "schema_version": "0.1",
  "status": "READY",
  "space_count": 4,
  "opening_count": 6,
  "blockers": []
}
```

or a fail-closed result such as:

```json
{
  "schema_version": "0.1",
  "status": "BLOCKED",
  "space_count": 4,
  "opening_count": 5,
  "blockers": [
    {
      "entity_id": "door-global-id",
      "reason": "AMBIGUOUS_SPACE_ADJACENCY"
    }
  ]
}
```

The schema is published at:

`schemas/ifc-control-readiness-v0.1.schema.json`

## Non-goals

v0.1 does not claim:

- every valid IFC is control-ready;
- missing space adjacency can safely be inferred;
- bounding boxes are engineering-valid airflow geometry;
- IFC replaces CONTAM or another physics engine.

The gate is intentionally stricter than "the file opened successfully."

## Infrastructure position

The intended reusable boundary is:

```text
IFC / other open building representation
          ↓
control-readiness gate
          ↓
AirTrajectory Layout Contract
          ↓
physics adapter
          ↓
trajectory / policy
          ↓
physical device feedback
```

A third party can adopt the readiness vocabulary or schema without adopting the
rest of AirTrajectory.


## Reproducible IFC importer environment

The optional IFC path is intentionally isolated from the core runtime.

```bash
python -m pip install -r requirements-ifc.txt
python examples/import_ifc_layout.py model.ifc --out model.airtrajectory.json
python examples/verify_imported_topology.py model.airtrajectory.json
```

The pinned importer dependency is currently `ifcopenshell==0.9.0`.

A future importer-version update must preserve the source provenance and rerun
the external corpus/readiness regression before compatibility is claimed.
