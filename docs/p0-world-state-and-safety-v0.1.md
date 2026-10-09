# P0 trust boundaries: canonical world snapshot v0.1

This is a **new opt-in** immutable software contract, not a completed
repository-wide migration and not a new physical-control authorization.

`CanonicalWorldState.from_parts` validates:
- non-colliding topology IDs, finite positive zone volumes/opening areas;
- complete opening/zone coverage and non-finite value rejection;
- explicit missing environmental metrics (`null`, never fabricated);
- rain as `true`, `false`, or **unknown** (`null`);
- unique hardware/sensor bindings scoped to known topology IDs;
- deterministic canonical SHA-256 of the *whole* origin, not just opening %;
- provenance classes E1 (test/fixture), E2 (toy) and E3 (real
  simulator/public IFC/external adapter), with an explicit E3 source
  receipt fingerprint.

The API **rejects self-asserted E4 field proof and E5 external adoption**.
Even E3's SHA-256 only detects content mismatch; it does not independently
verify the upstream run. `execution_authorized` is always false.

## Example

```python
from airtrajectory.world_state import CanonicalWorldState, EvidenceRef

world = CanonicalWorldState.from_parts(
    topology=topology,
    opening_pct={"W1": 0.0, "D1": 100.0},
    zone_environment={
        "living": {"co2_ppm": 1200.0, "pm25_ug_m3": None},
        "bedroom": {"co2_ppm": 900.0, "pm25_ug_m3": None},
    },
    rain=None,
    observed_at=123456.0,
    evidence=EvidenceRef("E2", "toy-simulator", "test-case-01"),
)
world.assert_same_origin(world.sha256)
```

This snapshot is a **data-consistency input** for future adapters, not a
replacement for the existing commissioning, authorization-use freshness,
sensor ThingModel binding or post-action physical feedback verification.

## Actual P0 safety changes in the same PR

- Reject duplicate room/opening IDs before the map can overwrite them.
- Reject future, duplicate and non-finite critical single-window sensor
  readings instead of silently choosing the last reading.
- Validate the entire single-window action batch before sending any
  irreversible command.
- Validate all multi-window action IDs and percentages before dispatch;
  missing rain no longer silently becomes `False`; increasing an exterior
  window requires an explicit dry rain reading.

## Still open

- No distributed atomic transaction across multiple physical drivers.
  A partial transport failure after the first command remains possible.
- The multi-window demo bus does not yet enforce a fresh, independently
  verified sensor/hardware identity at each dispatch. It must not be used
  as a field safety gate without that integration.
- `CanonicalWorldState` is not yet wired into every physics, planner,
  trajectory, replay or physical module; the migration needs explicit
  adapters and regression tests rather than deleting loose dicts blindly.
- No physically measured τ₀ or independently adopted SDK is asserted.
