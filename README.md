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

## Verified capability matrix

| Capability | Status | Evidence boundary |
| --- | --- | --- |
| Multi-room / multi-window scenario simulator | ✅ verified | deterministic toy/surrogate physics; not engineering truth |
| Agent → safety gate → executed action → reward → trajectory | ✅ verified | proposed/executed/intervention are preserved |
| Behavior Cloning baseline | ✅ verified | topology-local discrete policy trained from behavior rows |
| Offline RL baseline | ✅ verified | conservative batch fitted-Q; unseen actions remain unavailable |
| Unseen-topology benchmark | ✅ verified | train on 2–4 rooms, evaluate on unseen 5-room chains |
| Spatial Episode Lab | ✅ verified | generated from the Python benchmark artifact |
| Counterfactual fork runtime | ✅ verified | strict full-state HTTP origin; no hidden state invention |
| CONTAM adapter | ✅ verified | official `contamxpy==0.0.9` + real NIST PRJ executes in Windows CI |
| WindowPilot runtime bridge | ✅ verified | runtime capabilities/readiness are discovered over HTTP and fail closed when provenance is incomplete |
| WindowPilot hardware integration path | ✅ software-verified | CWDS-CA01 driver lives in WindowPilot; AirTrajectory requires matching commissioning/runtime identity |
| Real device commissioning | ❌ not captured | requires real gateway endpoint/auth/device ID and a physical READ → OPEN 5% → STOP → CLOSE pass |
| Physical τ₀ | ❌ not captured | requires preflight lineage, commissioned hardware identity, fresh measured sensors, actual movement, and post-action evidence |

The fast multizone backend remains a learning surrogate. CONTAM is now an executable higher-fidelity backend, but a real room trajectory is still the final evidence gate.

## Quick start

```bash
python -m unittest discover -s tests -v
python examples/single_room_rollout.py
```

The single-room demo writes a trajectory to:

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

## Next gates

1. Supply the real WindowPilot gateway contract: property set/get endpoints, device ID, authentication, timestamp path, quality path, and measured-position source.
2. Run WindowPilot read-only preflight, then the bounded `READ → OPEN 5% → STOP → CLOSE` commissioning sequence on one real window.
3. Start WindowPilot hardware mode with fresh measured CO₂/rain evidence and capture the first audited physical τ₀.
4. Add topology compilation from the real ThingModel/floor-plan source rather than generated chain scenarios.
5. Expand the learning stack and quantify sim→real transfer on held-out structural families.

## Physical τ₀ evidence chain

AirTrajectory now accepts a commissioning bundle only when it carries the WindowPilot read-only preflight lineage:

```text
read-only preflight PASS
→ preflight receipt SHA-256
→ preflight hardware identity
→ gateway contract SHA-256
→ bounded commissioning PASS
→ same runtime hardware identity
→ fresh measured CO₂ + rain
→ real window command
→ post-command measured position
→ newer post-action environment sample
→ τ₀ audit PASS
```

The capture CLI is:

```bash
python examples/capture_physical_tau0.py \
  --windowpilot http://127.0.0.1:8001 \
  --commission-bundle /path/to/physical-bringup.json \
  --out artifacts/physical-tau0.jsonl \
  --receipt artifacts/physical-tau0-audit.json
```

Older commissioning bundles that do not prove the read-only preflight lineage are rejected before AirTrajectory asks WindowPilot for a physical command.

## Non-goals

AirTrajectory is not a window actuator driver, not a BMS, and not a UI dashboard. Those are integration surfaces, not the learning core.


### Counterfactual fork contract

A UI or device session can send an immutable post-action origin into `airtrajectory.api.fork_request(payload)`. The core contract is transport-neutral: HTTP/MQTT/local adapters can wrap it without changing fork semantics. Today it intentionally accepts only the explicit `demo-3zone` topology; unknown topologies fail closed rather than borrowing demo physics. Returned branches are labeled `backend-generated · toy-multizone-v1 · not engineering truth`.


### Decision telemetry

Every backend counterfactual request writes a local JSONL decision trace even when no observability backend is installed. Install `.[telemetry]` and call `configure_otlp()` to export the same spans over OTLP; this keeps Phoenix, an OpenTelemetry Collector, or another OTLP-compatible backend replaceable. Telemetry is observational and must not block the control path.
