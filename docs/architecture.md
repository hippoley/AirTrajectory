# Architecture

AirTrajectory is a topology-aware ventilation trajectory system. It is not a
generic agent platform and not a device runtime.

## Product invariant

The same downstream control semantics must survive changes in:

- floor plan;
- room count;
- door/window count;
- opening placement;
- physics backend;
- policy/model implementation;
- device runtime.

The primary path is:

```text
Floorplan / structured layout
        ↓
Canonical Topology Contract
        ↓
Environmental State Contract
        ↓
Candidate Ventilation Paths / Joint Action Space
        ↓
Physics Adapter
Fast model / CONTAM / CFD / calibrated model
        ↓
Trajectory Candidates
        ↓
Policy / Ranking / Optimization
        ↓
Safety + execution boundary
        ↓
WindowPilot / BMS / actuator adapter
        ↓
Measured feedback
        ↓
Next physical origin
        ↓
Replan / learn
```

## Stable contracts

### 1. Topology Contract

Must represent variable-size:

- rooms / zones;
- walls;
- internal doors/openings;
- exterior windows/vents;
- indoor/outdoor connectivity;
- opening placement and geometry when available.

No core planner should require fixed identifiers such as W1/W2/W3.

### 2. Environmental State Contract

Target zone/boundary state includes:

- CO₂;
- PM2.5;
- temperature;
- relative humidity;
- TVOC;
- formaldehyde / HCHO;
- occupancy / source terms where available;
- outdoor weather / pollutant boundary conditions.

Values must preserve evidence class: measured, estimated, simulated, stale, or unavailable.

### 3. Trajectory Contract

A trajectory preserves:

- topology/environment origin;
- user/system objective;
- proposed coordinated action;
- executed action;
- interventions;
- predicted future;
- measured future when available;
- reward / outcome vector;
- provenance.

Never rewrite an override as though the policy proposed it.

### 4. Physics Adapter Contract

The planner must be able to use replaceable physics backends without changing
the topology or trajectory semantics.

### 5. Physical Adapter Contract

Device runtimes own hardware protocols and local safety. AirTrajectory owns the
physical-action intent, expected result, measured feedback binding, and next
trajectory origin.

## Ownership boundaries

### AirTrajectory owns

- canonical topology;
- environmental state abstraction;
- candidate ventilation-path generation;
- physics-backend adapters;
- trajectory generation;
- multi-objective evaluation;
- policy / optimization benchmarks;
- transfer evaluation;
- sim→real comparison.

### Device runtimes own

- actuator protocol;
- local device safety;
- transport/authentication;
- manual override;
- raw device telemetry.

## Generalization target

Evaluation must split by topology, not just by random transition.

The ladder is:

1. parameter generalization;
2. room/window-count generalization;
3. structural-topology generalization;
4. multi-environment objective generalization;
5. device adapter generalization;
6. sim→real generalization.

The research claim should only advance when the matching rung has evidence.

## Development ordering

A new feature is high priority when it unlocks one of:

```text
arbitrary floorplan
→ variable topology
→ multi-environment objective
→ joint strategy
→ physical feedback
→ held-out transfer
```

Correctness, evidence, playable probes, PPEP, and interoperability work are
supporting layers. They are valuable when they make this path safer, more
reproducible, or easier for another system to adopt. They should not redefine
the product surface.
