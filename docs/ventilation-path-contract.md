# VentilationPath Contract v0.1

The VentilationPath contract is AirTrajectory's semantic seam between building metadata and ventilation control.

It is intentionally **not** a building ontology and **not** a controller.

```text
Brick / Haystack / ASHRAE 223 / CAD / custom topology
                    ↓
             Topology Contract
                    ↓
          VentilationPath Contract
                    ↓
   CONTAM / CFD / MPC / RL / rule policy
                    ↓
         Policy Benchmark Contract
                    ↓
       physical execution / reconcile
```

## Why this layer exists

Building ontologies can identify spaces, windows, doors, sensors and equipment. Controllers can optimize actions. A natural-ventilation system still needs a portable control semantic for the *route through the building* that a coordinated set of openings is intended to activate.

A path such as:

```text
outside → W1 → living → D2 → study → W3 → outside
```

is represented independently of:

- whether CONTAM, CFD or a learned surrogate evaluates it;
- whether a rule, MPC, RL or future foundation model selects it;
- which actuator protocol eventually moves the windows.

## v0.1 semantics

Discovery is deterministic and connectivity-only.

A v0.1 path records:

- two exterior opening endpoints;
- any internal openings between them;
- traversed zones;
- the complete ordered opening sequence;
- bottleneck opening area;
- topology identity/hash;
- an explicit `effectiveness=unverified` boundary.

The contract does **not** claim that every topological path creates useful airflow. Physics and field evidence are deliberately separate layers.

## Durable infrastructure target

A third-party project should be able to:

1. provide its own topology;
2. emit or consume `ventilation-path-v0.1`;
3. evaluate those paths with its own physics engine;
4. report results through the AirTrajectory Policy Benchmark Contract.

That keeps the reusable artifact valuable even if the preferred simulator, controller, or foundation model changes.
