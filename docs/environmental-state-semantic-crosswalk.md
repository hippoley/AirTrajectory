# Environmental State Semantic Crosswalk v0.1

AirTrajectory does **not** define a replacement building ontology.

The Environmental State Contract is a trajectory/control envelope layered above
existing building metadata and point semantics.  Integrations SHOULD preserve
upstream semantic identifiers when available.

## Project Haystack 4 mapping guidance

| AirTrajectory field | Haystack semantic concept |
|---|---|
| `co2_ppm` | zone + air + `co2-concentration` + sensor + point |
| `pm25_ug_m3` | zone + air + `pm25-concentration` + sensor + point |
| `temperature_c` | zone + air + temp + sensor + point |
| `relative_humidity_pct` | zone + air + humidity + sensor + point |
| `tvoc_ug_m3` | zone + air + `tvoc-concentration` + sensor + point |
| `hcho_mg_m3` | zone + air + `ch2o-concentration` + sensor + point |
| `occupancy_count` | occupied/occupancy-related zone point where available |
| outdoor temperature | weather + air + temp sensor point |
| outdoor relative humidity | weather + air + humidity |
| wind speed | weather + wind + speed |
| wind direction | weather + wind + direction |
| rain | weather condition / precipitation according to source semantics |
| pressure | weather + atmospheric pressure |

Haystack distinguishes sensor, synthetic/computed, and simulation point
functions.  AirTrajectory keeps a separate evidence classification because a
trajectory must also distinguish stale and unavailable values and must not
silently promote an estimate into a measurement.

## Brick / BuildingMOTIF boundary

Brick, BuildingMOTIF, Haystack, ASHRAE 223 and similar systems are appropriate
upstream sources for asset/space/point semantics.

AirTrajectory's added responsibility begins at the control-learning boundary:

```text
upstream building semantics
        ↓
Topology / point adapter
        ↓
Environmental State + evidence class
        ↓
VentilationPath / policy candidates
        ↓
trajectory / benchmark / physical reconciliation
```

The interoperability goal is therefore adapter compatibility, not ontology
replacement.

## Durable identity principle

A third party should be able to:

1. retain Brick/Haystack/223 semantics;
2. project observations into `environmental-state-v0.1`;
3. run its own simulator/controller;
4. emit an AirTrajectory policy benchmark receipt.

That makes the contracts independently adoptable without requiring the full
AirTrajectory application.