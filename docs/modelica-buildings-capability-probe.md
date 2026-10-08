# Modelica Buildings capability probe

This note records the current verified boundary between AirTrajectory
VentilationPath semantics and LBL's Modelica Buildings multizone airflow
library.

## Verified

- `Buildings.Airflow.Multizone.DoorOperable`
- `Buildings.Airflow.Multizone.DoorDiscretizedOperable`

Both expose a normalized opening input `y in [0,1]` and are explicitly
documented as operable bi-directional room-to-room openings.

The multizone package also supports contaminant transport.

## Not yet verified

AirTrajectory does **not** currently map an exterior operable window to a
specific Modelica Buildings component.

That gap is intentional.  A door model, an orifice, and an operable exterior
window are not interchangeable physical semantics merely because all involve
an opening.

The adapter therefore fails closed for any VentilationPath that requires an
exterior window until a validated mapping exists.

## Why this matters

A second physics backend is useful only if it provides independent evidence.
Pretending that unsupported opening semantics are supported would produce a
false cross-backend confirmation.

The durable target is:

```text
VentilationPath
   ├─ CONTAM mapping
   ├─ Modelica Buildings mapping
   ├─ selected CFD mapping
   └─ physical evidence
```

Each backend must declare its supported opening semantics explicitly.
