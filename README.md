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

## Layout contract: fixed now, replaceable later

The current interactive lab intentionally keeps room and wall geometry fixed while allowing every declared window and door to move along its own wall and change opening state.

`web/data/home_topology.fixed.json` is now the layout source of truth for the browser. Its contract explicitly declares:

```text
floorplan_geometry_editable = false
opening_position_editable   = true
opening_state_editable      = true
arbitrary_topology_import   = reserved
contam_compiler             = reserved
```

This is a staging boundary, not a permanent limitation. The renderer consumes the layout contract rather than owning room geometry. A future 2D-plan importer can emit the same contract, and a future topology → CONTAM compiler can consume it without changing the current door/window interaction model.

Moving a door or window changes its normalized `position_t`, increments the topology revision, and makes old trajectory results stale. Room and wall geometry remain locked in the current release.

The Python `LayoutContract` independently validates this fixed-layout boundary and projects the same file into the existing graph-level `BuildingTopology`. That keeps UI geometry and learning connectivity behind one contract instead of two hand-maintained topology definitions.

The same contract now exposes both downstream seams explicitly:

```python
layout.trajectory_context(
    topology_revision=3,
    opening_positions={"W1": 0.72, "D1": 0.25},
)

layout.contam_compile_contract(
    opening_positions={"W1": 0.72, "D1": 0.25},
)
```

Both receive the same normalized opening positions. Moving an opening changes its wall position but not its room connectivity. The CONTAM method currently returns `status=RESERVED` with zone/wall/opening inputs and empty PRJ/control/path outputs; it is a real compiler seam, not a claim that arbitrary topology → CONTAM compilation is finished.

## Verified capability matrix

| Capability | Status | Evidence boundary |
| --- | --- | --- |
| Fixed layout → UI / trajectory contract | ✅ verified | one `home_topology.fixed.json`; room/wall geometry locked, window/door wall position editable |
| Layout → CONTAM compiler seam | 🟡 reserved | same opening positions flow into `contam_compile_contract()`; PRJ/control/path generation remains intentionally unimplemented |
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
| Real device commissioning | ❌ not captured | reserved real-hardware gate; requires real gateway endpoint/auth/device ID and a physical READ → OPEN 5% → STOP → CLOSE pass |
| Physical τ₀ zero-motion preflight | ✅ software-verified | one shared gate revalidates commissioning behavior, write readiness, identity/site/ThingModel continuity, and live CO₂/rain lineage before any motion |
| Physical τ₀ | ❌ not captured | reserved real-evidence gate; requires preflight PASS plus actual movement, measured actuator feedback, and newer post-action sensor evidence |
| Mock hardware fallback | ✅ runnable | deterministic mock API/actuator path keeps the interaction loop usable while real integration is unavailable; never promoted as hardware evidence |
| Mock τ_sim artifact | ✅ runnable | `web/data/mock_physical_fallback.json`; `physical_evidence=false`, illustrative simulation only |

The fast multizone backend remains a learning surrogate. CONTAM is now an executable higher-fidelity backend, but a real room trajectory is still the final evidence gate.

The real-device rows above are intentionally **not removed when hardware is unavailable**. The web console keeps those gates visible as `REAL / RESERVED` and activates a clearly labeled mock fallback beside them. The bundled fallback starts from the illustrative single-room seed used during development: 30 m² / 75 m³, 2 occupants, indoor CO₂ 1400 ppm, outdoor CO₂ 430 ppm, dry weather, 0% initial opening, 1.5 m/s wind and a 20% simulated target. Its trajectory is `τ_sim`, not `physical τ₀`.

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
→ locked ThingModel product/source/registry/contract lineage
→ physical-site manifest lineage (site / room / installed device instance)
→ bounded commissioning PASS
→ independently revalidated acceptance policy:
   excursion ≤5% + tolerance ≤1% + STOP samples ≥2
→ independently revalidated behavior witness:
   initial closed + OPEN positive delta + STOP hold + CLOSE negative delta
→ commissioning behavior SHA-256 (policy + measured behavior)
→ same runtime hardware + same ThingModel + same physical-site lineage
→ fresh measured CO₂ + rain with verified product-property + site-instance bindings
→ runtime sensor source lineage (timestamp / quality / source / binding)
→ optional stronger proof: CO₂ + rain sensor_apply receipts
   live source contract == staged receipt contract
   same commissioning/runtime/site identity
   zero actuator/window commands during staging
→ sensor evidence SHA-256
→ real window command
→ post-command measured position
→ newer post-action CO₂/rain with the same ThingModel + site-instance provenance
→ τ₀ audit PASS
```

The physical gate is deliberately split into three stages. First run the **zero-motion preflight**; it contacts WindowPilot but issues no actuator command:

```bash
python examples/check_physical_tau0_preflight.py \
  --windowpilot http://127.0.0.1:8001 \
  --commission-bundle /path/to/physical-bringup.json \
  --receipt artifacts/physical-tau0-preflight.json
```

A preflight PASS proves the commissioning bundle, current runtime identity, write gate and live sensor lineage are mutually consistent. It does **not** count as physical τ₀ because no trajectory motion has happened.

Only after that gate is green, run the capture CLI:

```bash
python examples/capture_physical_tau0.py \
  --windowpilot http://127.0.0.1:8001 \
  --commission-bundle /path/to/physical-bringup.json \
  --out artifacts/physical-tau0.jsonl \
  --receipt artifacts/physical-tau0-audit.json

# Optional stronger source audit, only when both roles were staged through
# WindowPilot execution.sensor_apply:
python examples/capture_physical_tau0.py \
  --windowpilot http://127.0.0.1:8001 \
  --commission-bundle /path/to/physical-bringup.json \
  --sensor-apply-receipt /path/to/sensor-runtime-apply.co2.json \
  --sensor-apply-receipt /path/to/sensor-runtime-apply.rain.json \
  --out artifacts/physical-tau0.jsonl \
  --receipt artifacts/physical-tau0-audit.json
```

Both the zero-motion preflight and the capture CLI call the same `validate_physical_tau0_preconditions()` function, so the read-only gate cannot silently drift from the rules used immediately before motion. Older commissioning bundles are rejected before AirTrajectory asks WindowPilot for a physical command unless they prove read-only preflight lineage, WindowPilot schema >=0.3 behavior evidence, and the bounded commissioning acceptance policy. AirTrajectory independently reconstructs that policy and rejects missing or weakened criteria. A mere `status=PASS`, four phase labels, or a self-asserted witness are not sufficient.

Sensor source evidence has deliberately separate levels:

```text
runtime-measured-lineage
  fresh + measured + ThingModel/site-bound
  source/timestamp/quality visible
  transport can be GET, MQTT, push, or another verified adapter

probe-labeled
  both live sources say sensor-read-probe:<contract-sha>
  descriptive only — NOT audited staging

probe-apply-audited
  exactly two WindowPilot sensor_apply PASS receipts (CO₂ + rain)
  same commissioning/runtime/site lineage
  live contract SHA == staged contract SHA
  staging proved observe-only and zero actuator/window commands
```

Supplying only one apply receipt fails closed rather than creating a partial audited state.

After capture, re-verify the persisted artifacts independently:

```bash
python examples/verify_physical_tau0.py \
  --trajectory artifacts/physical-tau0.jsonl \
  --receipt artifacts/physical-tau0-audit.json \
  --commission-bundle /path/to/physical-bringup.json
```

This verifier does not contact hardware. It re-checks:

```text
trajectory SHA-256
+ commissioning bundle SHA-256
+ commissioning/runtime/preflight identity continuity
+ ThingModel productKey/source/registry/contract lineage
+ physical-site / room / device-instance lineage
+ site manifest / instance / site-contract SHA-256 continuity
+ gateway contract lineage
+ commissioning acceptance policy / behavior witness / SHA-256
+ policy cannot weaken excursion, tolerance, STOP-sample or timestamp requirements
+ READ near-closed, OPEN positive delta, STOP multi-sample hold, CLOSE negative delta
+ strictly increasing commissioning source timestamps
+ runtime CO₂/rain source lineage + sensor evidence SHA-256
+ optional probe-apply staging lineage when the receipt claims audited staging
+ measured actuator position
+ pre-action CO₂/rain ThingModel + site-instance provenance
+ newer post-action CO₂/rain ThingModel + site-instance provenance
```

AirTrajectory deliberately does **not** copy the raw vendor ThingModel bundle or the private deployment manifest. WindowPilot owns product-registry and physical-site validation; AirTrajectory carries only the non-secret site/room/device-instance identity plus cryptographic lineage required to prove that the same verified installed device produced the physical trajectory.

The physical closeout is complete only when capture returned `valid_tau0=true` **and** this independent artifact verification returns `valid_artifacts=true`.

## Non-goals

AirTrajectory is not a window actuator driver, not a BMS, and not a UI dashboard. Those are integration surfaces, not the learning core.


### Counterfactual fork contract

A UI or device session can send an immutable post-action origin into `airtrajectory.api.fork_request(payload)`. The core contract is transport-neutral: HTTP/MQTT/local adapters can wrap it without changing fork semantics. Today it intentionally accepts only the explicit `demo-3zone` topology; unknown topologies fail closed rather than borrowing demo physics. Returned branches are labeled `backend-generated · toy-multizone-v1 · not engineering truth`.


### Decision telemetry

Every backend counterfactual request writes a local JSONL decision trace even when no observability backend is installed. Install `.[telemetry]` and call `configure_otlp()` to export the same spans over OTLP; this keeps Phoenix, an OpenTelemetry Collector, or another OTLP-compatible backend replaceable. Telemetry is observational and must not block the control path.
