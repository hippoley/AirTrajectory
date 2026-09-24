# AirTrajectory

**Trajectory-native learning for multi-zone, multi-window ventilation control.**

AirTrajectory turns room topology + a replaceable physics backend into trajectories that can be used for offline RL, sequence models, counterfactual analysis, and transfer evaluation on unseen floor plans.

## North star

> Learn transferable multi-window ventilation strategies from simulated and real trajectories, then generalize them to unseen building topologies.

This repository is deliberately decoupled from device runtimes such as WindowPilot. AirTrajectory owns learning, simulation adapters, trajectory data, and transfer benchmarks. Device runtimes integrate through adapters.

## Architecture

```text
Floor plan / topology
        ↓
Topology compiler
        ↓
Physics backend
Fast model / CONTAM / CFD adapter
        ↓
Trajectory factory
        ↓
Offline RL / Decision Transformer / MARL
        ↓
Unseen-topology benchmark
        ↓
Deployment adapter
        ↓
Real devices / WindowPilot / BMS
        ↓
Real trajectories back into AirTrajectory
```

## What already runs

- topology-native zones and openings
- replaceable environment contract
- deterministic fast multizone baseline
- training-grade trajectory schema
- proposed vs executed action separation
- vector rewards
- JSONL trajectory store
- deterministic rollout demo
- unit tests for topology + trajectory plumbing

The fast multizone backend is **not** an engineering airflow solver. It exists so the learning pipeline is runnable before CONTAM is connected.

## Quick start

```bash
python -m unittest discover -s tests -v
python examples/single_room_rollout.py
```

The demo writes a trajectory to:

```text
artifacts/trajectories.jsonl
```

## Project layout

```text
airtrajectory/
  topology.py
  trajectory.py
  environment.py
  rollout.py
examples/
  single_room_rollout.py
tests/
  test_core.py
docs/
  architecture.md
```

## Roadmap

1. Safety resolver and explicit intervention trajectories
2. CONTAM backend adapter
3. Floor-plan / ThingModel → topology compiler
4. Counterfactual branching from any trajectory step
5. Offline-RL + Decision Transformer dataset exporters
6. Train / validation / unseen-topology benchmark splits
7. WindowPilot and BMS deployment adapters

## Non-goals

AirTrajectory is not a window actuator driver, not a BMS, and not a UI dashboard. Those are integration surfaces, not the learning core.


### Counterfactual fork contract

A UI or device session can send an immutable post-action origin into `airtrajectory.api.fork_request(payload)`. The core contract is transport-neutral: HTTP/MQTT/local adapters can wrap it without changing fork semantics. Today it intentionally accepts only the explicit `demo-3zone` topology; unknown topologies fail closed rather than borrowing demo physics. Returned branches are labeled `backend-generated · toy-multizone-v1 · not engineering truth`.


### Decision telemetry

Every backend counterfactual request writes a local JSONL decision trace even when no observability backend is installed. Install `.[telemetry]` and call `configure_otlp()` to export the same spans over OTLP; this keeps Phoenix, an OpenTelemetry Collector, or another OTLP-compatible backend replaceable. Telemetry is observational and must not block the control path.
