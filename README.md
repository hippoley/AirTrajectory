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

Both receive the same normalized opening positions. Moving an opening changes its wall position but not its room connectivity. The current fixed-layout path now continues through metric overlay → CONTAM IR → deterministic writer manifest → airflow/boundary/PRJ profiles → generated `.prj`; arbitrary topology import is still reserved.

A backend-neutral spatial compile plan now sits between that contract and future physics compilers:

```python
from airtrajectory.spatial_compile import compile_spatial_plan

plan = compile_spatial_plan(
    layout,
    opening_positions={"W1": 0.72, "D1": 0.25},
)
```

It resolves each normalized `position_t` to a deterministic anchor on its declared wall and assigns stable symbolic `zone:*`, `path:*`, and `control:*` identities. Moving a window changes its placement anchor while preserving connectivity identity. The current fixed floor plan uses browser/canvas coordinates, so the plan does **not** pretend that UI coordinates are metres.

The layout schema now also accepts optional physical geometry without fabricating it: walls may provide `length_m` + `azimuth_deg`, and openings may provide `width_m` + `height_m` + `sill_height_m`. The spatial compiler reports missing fields per wall/opening, flips `metric_geometry_ready=true` only when the whole layout is physically specified, and derives `distance_along_wall_m = position_t × length_m`. Invalid azimuths, non-positive dimensions, openings wider than their wall, or `max_area_m2` larger than the physical opening area fail closed. Complete metric inputs can now proceed into the real generated-PRJ path; illustrative geometry remains explicitly non-engineering evidence.

Once metric inputs are complete, `airtrajectory.contam_ir.compile_contam_ir()` turns the spatial plan into a CONTAM-oriented symbolic IR. It creates stable `zone:*`, `wall:*`, `path:*`, `control:*`, and `ambient:OUTSIDE` identities, distinguishes exterior ambient paths from internal zone-to-zone paths, and carries metric opening placement into the physics boundary. Numeric CONTAM zone/path/control IDs, airflow-element selection, wind/weather profiles, contaminant definitions, and PRJ serialization are now implemented for the current fixed-layout demo path. General arbitrary-topology PRJ coverage remains a later expansion gate.

The writer path uses `airtrajectory.contam_allocator.allocate_contam_ids()` to assign deterministic 1-based numeric IDs by lexicographically sorting symbolic keys, so source JSON ordering does not affect the generated mapping. The allocator emits a `mapping_sha256` for replay/audit, and moving a door or window preserves its numeric path/control identity as long as the symbolic topology identity is unchanged. The current fixed-layout pipeline then binds airflow elements, weather/contaminants, explicit PRJ fields, and serializes a real ContamX-loadable project.

Airflow-element binding is now explicit rather than implicit. `airtrajectory.contam_profile.bind_airflow_elements()` requires a named profile with per-opening-kind rules. The bundled demo profile is intentionally marked `engineering_validated=false`; production callers can set `require_engineering_validated=True` to reject it. The current supported semantic model is `powerlaw-orifice-area`, carrying flow area, flow exponent, discharge coefficient, and an optional hydraulic diameter into deterministic `element:*` identities. These parameters align with the parameterization described in the NIST CONTAM user guide, but project-specific engineering calibration remains outside the demo preset.

Ambient forcing is now explicit as well. `airtrajectory.contam_boundary.bind_boundary_profile()` attaches wind speed/direction, outdoor temperature, barometric pressure, and contaminant definitions to the bound manifest. Each contaminant must provide an outdoor concentration and an initial concentration for every modeled zone; missing or unknown zones fail closed. The boundary profile carries its own SHA-256 and can also be gated by `engineering_validated=true`, so demo weather/CO₂ assumptions cannot silently become production evidence.

## Verified capability matrix

| Capability | Status | Evidence boundary |
| --- | --- | --- |
| Fixed layout → unified demo runtime snapshot | ✅ verified | one topology revision + opening state/position snapshot drives UI payload, physics input, and trajectory provenance |
| Layout → spatial compile plan | ✅ verified | `position_t` resolves to deterministic wall anchors; path/control identities remain stable across moves |
| Spatial plan → CONTAM IR | ✅ verified | metric-ready layouts compile into stable symbolic zones/paths/controls/ambient boundaries |
| CONTAM IR → deterministic writer manifest | ✅ verified | symbolic zones/paths/controls receive stable 1-based numeric IDs with mapping SHA-256 |
| Writer manifest → airflow-element binding | ✅ verified | explicit profile binds deterministic `element:*` identities; production gate rejects illustrative profiles |
| Bound manifest → boundary forcing | ✅ verified | wind/weather + contaminant profiles are explicit, hashed, zone-complete, and production-gated |
| Forced manifest → PRJ readiness audit | ✅ verified | section/entity-level blockers are explicit and hashed; no file is emitted while incomplete |
| Explicit PRJ profile → serialization readiness | ✅ verified | Section 10/14/15/16 + project/species/levels can be made complete without hidden defaults |
| Serialization-ready manifest → generated PRJ | ✅ verified | deterministic 3-zone/5-path PRJ generated from the shared topology pipeline |
| Generated PRJ → real ContamX airflow | ✅ verified | Windows CI loads 3 zones/5 paths, advances solver, and requires non-zero net path flow |
| Dynamic opening % → ContamX input controls | ✅ verified | W1/W2/W3 named input controls execute in real ContamX; 0% mechanical close maps to an explicit leakage floor instead of deleting the exterior path |
| Multi-room / multi-window scenario simulator | ✅ verified | deterministic toy/surrogate physics; not engineering truth |
| Agent → safety gate → executed action → reward → trajectory | ✅ verified | proposed/executed/intervention are preserved |
| Behavior Cloning baseline | ✅ verified | topology-local discrete policy trained from behavior rows |
| Offline RL baseline | ✅ verified | conservative batch fitted-Q; unseen actions remain unavailable |
| Unseen-topology benchmark | ✅ verified | train on 2–4 rooms, evaluate on unseen 5-room chains |
| Spatial Episode Lab | ✅ verified | generated from the Python benchmark artifact |
| Counterfactual fork runtime | ✅ verified | strict full-state HTTP origin; no hidden state invention |
| CONTAM adapter | ✅ verified | official `contamxpy==0.0.9` + real NIST PRJ executes in Windows CI |
| Unified rule policy → real CONTAM trajectory | ✅ verified | the same `DemoRuntimeSnapshot` + `MultiWindowRuleAgent` executes multi-step W1/W2/W3 actions against generated ContamX PRJ and emits the shared trajectory schema |
| WindowPilot runtime bridge | ✅ verified | runtime capabilities/readiness are discovered over HTTP and fail closed when provenance is incomplete |
| Multi-window physical execution bus | ✅ software-verified | per-opening drivers/readiness/measured feedback; any unready commanded window blocks the dispatch |
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

## One-command physical field handoff

The safest field entry point is now a single orchestrator. It is **read-only by
default**:

```bash
python examples/run_physical_field_handoff.py \
  --windowpilot http://127.0.0.1:8001 \
  --commission-bundle /path/to/physical-bringup.json \
  --opening-id W1 \
  --topology-id physical-single-window
```

Without `--execute`, it performs the zero-motion WindowPilot/AirTrajectory
preflight, persists a summary receipt with
`status=READY_FOR_EXPLICIT_EXECUTION`, and performs no actuator motion.

After reviewing that receipt, the bounded first-contact run must be explicitly
authorized:

```bash
python examples/run_physical_field_handoff.py \
  --windowpilot http://127.0.0.1:8001 \
  --commission-bundle /path/to/physical-bringup.json \
  --opening-id W1 \
  --topology-id physical-single-window \
  --execute
```

The execute path runs:

```text
zero-motion preflight
→ bounded τ₀ motion
→ verified WindowPilot command acknowledgement
→ measured actuator feedback
→ mandatory safe closeout
→ persisted-artifact independent verification
```

To bind a real-ContamX planner action and immediately produce a controller-ready
physical origin:

```bash
python examples/run_physical_field_handoff.py \
  --windowpilot http://127.0.0.1:8001 \
  --commission-bundle /path/to/physical-bringup.json \
  --opening-id W1 \
  --topology-id physical-single-window \
  --closed-loop-receipt artifacts/contam-closed-loop.json \
  --closed-loop-step-index 0 \
  --predicted-zone-id living \
  --current-origin artifacts/current-origin.json \
  --physical-origin-out artifacts/physical-next-origin.json \
  --execute
```

This still does **not** claim field validation until the artifacts come from a
real WindowPilot endpoint. The summary explicitly distinguishes read-only
readiness, executed physical evidence, and controller-ready physical origin.

## Replan from physical origin and execute the second field action

After the first field handoff emits a verified physical-origin receipt, real
ContamX can plan exactly one next action from that measured state:

```bash
python examples/run_contam_joint_closed_loop.py \
  artifacts/multispace-transient.prj \
  artifacts/multispace-transient.prj.json \
  --control-steps 1 \
  --prediction-horizon-steps 3 \
  --physical-origin-receipt artifacts/physical-next-origin.json \
  --out artifacts/contam-replan-from-physical-origin.json
```

When `--physical-origin-receipt` is present, the runner intentionally requires
`--control-steps 1`. Only that first plan is grounded in the measured field
origin; additional steps without another physical observation would be
simulation continuation.

The resulting next action is then bound back to the exact physical-origin hash
and must pass an explicit field ramp limit before another command can move:

```bash
python examples/run_replanned_physical_step.py \
  --windowpilot http://127.0.0.1:8001 \
  --physical-origin-receipt artifacts/physical-next-origin.json \
  --planner-receipt artifacts/contam-replan-from-physical-origin.json \
  --opening-id W1 \
  --zone-id living \
  --max-delta-pct 10
```

That command is read-only by default. It verifies:

```text
physical-origin receipt hash
→ real-ContamX planner origin hash
→ selected planner step hash
→ WindowPilot non-simulated measured-position capability
→ physical_write_ready
→ stable runtime hardware identity
→ bounded next-action authorization
```

Only after review should the same command be repeated with `--execute`.

Real execution also consumes the physical origin through a durable local
single-use lease. Keep the lease namespace stable across runs and output
directories. The CLI default is `artifacts/physical-origin-leases`; changing
`--summary-out` or `--next-origin-out` must not create a new lease namespace.

```bash
python examples/run_replanned_physical_step.py \
  --windowpilot http://127.0.0.1:8001 \
  --physical-origin-receipt artifacts/physical-next-origin.json \
  --planner-receipt artifacts/contam-replan-from-physical-origin.json \
  --opening-id W1 \
  --zone-id living \
  --max-delta-pct 10 \
  --lease-dir artifacts/physical-origin-leases \
  --next-origin-out artifacts/physical-next-origin-2.json \
  --execute
```

The execute path requires WindowPilot command acknowledgement v2. AirTrajectory
creates a fresh UUID `request_id` for each command; WindowPilot must echo that
challenge in the ACK and add its own UUID `command_id`. The ACK hash covers
both identities. Legacy v1 acknowledgements remain readable as historical
first-contact evidence, but they are not accepted for new replanned physical
cycles.

The Python API requires an explicit `lease_dir` whenever
`execute=True`; it will not infer a lease directory from an output path.
Claiming is atomic on one filesystem, so two local processes sharing the same
lease namespace cannot both consume the same physical-origin receipt. This is
still a local orchestration guarantee, not a distributed gateway/device
transaction guarantee.

The command evidence must also be temporally monotonic:

```text
fresh request_id
→ ACK accepted_at
→ measured actuator feedback timestamp
→ fresh CO₂/rain timestamps
```

The execute path requires measured actuator feedback and fresh CO₂/rain newer
than that feedback. It then emits another verified physical-origin receipt:

```text
physical origin #1
→ real ContamX one-step replan
→ bounded second WindowPilot command
→ verified command ACK
→ measured terminal position
→ fresh post-action CO₂/rain
→ physical origin #2
```

A planner jump is never silently treated as fully authorized. For example, if
the measured opening is 0.2%, the planner asks for 75%, and
`--max-delta-pct 10`, the authorized field target is 10.2% and the receipt
records `REPLANNED_ACTION_BOUNDED_BY_FIELD_RAMP_LIMIT`.

This path makes repeated physical closed-loop execution possible, but repository
CI still uses synthetic contract fixtures and does not claim real field
validation.

After an executed step, verify the persisted artifacts independently without
contacting hardware:

```bash
python examples/verify_replanned_physical_cycle.py \
  --previous-origin artifacts/physical-next-origin.json \
  --planner-receipt artifacts/contam-replan-from-physical-origin.json \
  --step-summary artifacts/replanned-physical-step.json \
  --next-origin artifacts/physical-next-origin-2.json \
  --out artifacts/physical-cycle-verification.json
```

The verifier re-derives the planner handoff and bounded authorization, checks
the complete command acknowledgement, measured actuator feedback and fresh
sensor snapshot, reconstructs the next physical origin, and requires it to
match the persisted next-origin receipt exactly. This proves persisted-artifact
contract continuity; it is still not a substitute for authenticated hardware
attestation.

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
→ latest measured position proves the window is initially closed (≤1%)
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
→ measured safe closeout to 0% after the trajectory
→ closeout timestamp newer than the final trajectory actuator feedback
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

Only after that gate is green, run the capture CLI. The τ₀ trajectory is
now exactly one bounded reality-contact action, not a ventilation-policy
rollout:

```text
preflight measured baseline <= commissioning tolerance
→ one OPEN probe target <= 5%
→ feedback timestamp newer than baseline
→ positive measured position Reality Delta >= 2 percentage points
→ measured position reaches the bounded target within tolerance
→ independent measured safe-closeout back to 0%
```

The probe target is also bounded by the excursion already approved by the
commissioning contract. AirTrajectory will not silently weaken the minimum
Reality Delta when a commissioning profile is too small to prove it.

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
+ τ₀ capture policy == physical-tau0-probe-v1
+ exactly one probe action with target <=5%
+ probe target bounded by the commissioned excursion
+ measured actuator feedback newer than the pre-action baseline
+ positive measured Reality Delta >= the persisted minimum threshold
+ measured probe position within the persisted target tolerance
+ runtime CO₂/rain source lineage + sensor evidence SHA-256
+ optional probe-apply staging lineage when the receipt claims audited staging
+ measured actuator position
+ pre-action CO₂/rain ThingModel + site-instance provenance
+ newer post-action CO₂/rain ThingModel + site-instance provenance
+ initially-closed measured baseline within the commissioning tolerance
+ post-trajectory measured closeout ≤1%
+ closeout feedback newer than the final trajectory actuator feedback
```

AirTrajectory deliberately does **not** copy the raw vendor ThingModel bundle or the private deployment manifest. WindowPilot owns product-registry and physical-site validation; AirTrajectory carries only the non-secret site/room/device-instance identity plus cryptographic lineage required to prove that the same verified installed device produced the physical trajectory.

The capture command also restores the commissioned closed baseline after the one-step Reality Delta probe. A successful audit receipt is not written unless that closeout is measured within the commissioning tolerance, and the independent verifier rejects missing, stale, estimated-only, or still-open closeout evidence.

The physical closeout is complete only when capture returned `valid_tau0=true` **and** this independent artifact verification returns `valid_artifacts=true`.

## Non-goals

AirTrajectory is not a window actuator driver, not a BMS, and not a UI dashboard. Those are integration surfaces, not the learning core.


### Counterfactual fork contract

A UI or device session can send an immutable post-action origin into `airtrajectory.api.fork_request(payload)`. The core contract is transport-neutral: HTTP/MQTT/local adapters can wrap it without changing fork semantics. Today it intentionally accepts only the explicit `demo-3zone` topology; unknown topologies fail closed rather than borrowing demo physics. Returned branches are labeled `backend-generated · toy-multizone-v1 · not engineering truth`.


### Decision telemetry

Every backend counterfactual request writes a local JSONL decision trace even when no observability backend is installed. Install `.[telemetry]` and call `configure_otlp()` to export the same spans over OTLP; this keeps Phoenix, an OpenTelemetry Collector, or another OTLP-compatible backend replaceable. Telemetry is observational and must not block the control path.

### CONTAM airflow profile gate

Demo-only binding:

```bash
python examples/bind_contam_airflow.py metric-layout.json \\
  --illustrative-demo-profile \\
  --out artifacts/contam-bound.json
```

Production-style gate:

```bash
python examples/bind_contam_airflow.py metric-layout.json \\
  --profile examples/contam_airflow_profile.example.json \\
  --require-engineering-validated \\
  --out artifacts/contam-bound.json
```

The example JSON demonstrates the schema only; its values still require review/calibration for the actual building before being treated as engineering evidence.

### CONTAM boundary forcing gate

```bash
python examples/bind_contam_boundary.py \
  metric-layout.json \
  examples/contam_boundary_profile.example.json \
  --illustrative-demo-airflow \
  --out artifacts/contam-forced.json
```

For production-style validation, supply an engineering-reviewed airflow profile and pass `--require-engineering-validated`. The bundled boundary example demonstrates the schema only; site weather and contaminant assumptions still require actual project evidence.

### CONTAM PRJ serialization readiness

Before writing a concrete `.prj`, AirTrajectory now performs a section-level readiness audit against the fields required by the NIST CONTAM 3.4 project format. The first-pass audit covers Section 10 (Airflow Elements), Section 14 (Zones), Section 15 (Initial Zone Concentrations), and Section 16 (Airflow Paths), plus the global project/species/level sections.

```bash
python examples/inspect_contam_prj_readiness.py \
  artifacts/contam-forced.json \
  --require-ready \
  --out artifacts/contam-prj-readiness.json
```

Incomplete manifests remain `BLOCKED` and report missing PRJ fields per section/entity rather than silently guessing them. The bundled fixed-layout demo supplies an explicit serialization profile that reaches `READY_FOR_PRJ_SERIALIZATION`; production use still requires engineering-validated metric, airflow, boundary, and PRJ profiles.

### CONTAM explicit PRJ profile

A concrete PRJ serialization profile can now fill the previously blocked Section 10/14/15/16 fields plus project controls, species definitions, and level records. The profile is explicit rather than inferred from UI geometry: every `path:*` record supplies its stored PRJ fields, zone state comes from declared defaults/overrides, and contaminant ppm values are converted to mass fraction using an explicit molecular-weight policy.

```bash
python examples/bind_contam_prj_profile.py \
  artifacts/contam-forced.json \
  examples/contam_prj_profile.example.json \
  --out artifacts/contam-prj-profiled.json \
  --readiness-out artifacts/contam-prj-readiness.json
```

With a complete profile, the readiness audit can now reach `READY_FOR_PRJ_SERIALIZATION`. The bundled example remains `engineering_validated=false`; it proves schema completeness and compiler behavior, not building-specific engineering truth.

### Multi-space / multi-window demo runtime

The demo now has one resolved runtime snapshot as the shared provenance boundary for UI, physics inputs, and trajectories. `DemoRuntimeSnapshot` carries the topology revision, opening positions, opening states, and a deterministic snapshot SHA-256. The same snapshot can render the browser payload, feed the physics compiler seam, and be embedded in trajectory context.

```bash
python examples/run_multispace_demo.py \
  --steps 10 \
  --topology-revision 1 \
  --out artifacts/multispace-demo.json
```

For real hardware, `MultiWindowPhysicalEnvironment` maps each physical opening to its own `PhysicalWindowDriver` / WindowPilot endpoint. Internal doors or other non-actuated openings can remain fixed topology state. Before any real movement, every commanded physical opening must report `physical_write_ready=true`; one blocked window blocks the entire dispatch. Measured position feedback is preserved per opening.

```text
one topology/config
→ DemoRuntimeSnapshot
├─ browser/UI payload
├─ physics/compiler input
└─ trajectory context

W1 → WindowPilot A ┐
W2 → WindowPilot B ├→ MultiWindowPhysicalEnvironment → one multi-window observation/step
W3 → WindowPilot C ┘
D1/D2 → fixed or separately actuated topology state
```

The current physical bus is software-verified only. It does not claim a real multi-window hardware run until the configured WindowPilot instances pass their own commissioning/write-readiness gates and return measured position feedback.

### Unified demo orchestration and physical endpoint mapping

`run_demo()` now executes the same `MultiWindowRuleAgent` against simulation, real CONTAM, or `MultiWindowPhysicalEnvironment`, while preserving the same `DemoRuntimeSnapshot` hash and trajectory schema. Physical trajectories now carry dedicated sensor evidence, post-action sensor evidence, and actuator feedback through the generic rollout path rather than a separate recorder.

The deployed UI also prefers `web/data/demo_runtime.generated.json`. GitHub Pages generates this artifact from `home_topology.fixed.json` at build time and validates its snapshot SHA against Python, avoiding a second hand-maintained UI topology source.

Real-window mapping is configuration-driven:

```text
W1 → WindowPilot endpoint A
W2 → WindowPilot endpoint B
W3 → WindowPilot endpoint C
D1/D2 → fixed topology state (until separately actuated)
```

Use the read-only preflight before any physical execution:

```bash
python examples/preflight_multispace_physical.py \
  --config examples/windowpilot_endpoints.example.json \
  --out artifacts/physical-preflight.json
```

This preflight never calls `set_position()` and therefore does not move hardware. It succeeds only when every configured physical opening reports `physical_write_ready=true`.

### Real generated CONTAM airflow smoke

The generated fixed-three-room project is exercised by the real `contamxpy==0.0.9` / ContamX 3.4.1.7 runtime in Windows CI. The gate requires the generated PRJ to load as exactly 3 zones / 5 paths, execute named W1/W2/W3 controls, and run a multi-step unified trajectory with the same rule policy used by the other demo backends. Mechanical 0% window state uses an explicit `closed_leakage_multiplier` (demo value 0.01) so a closed window retains modeled infiltration instead of mathematically disconnecting every exterior path.

This remains `engineering_truth=false`: the bundled metric geometry, boundary forcing, and serialization profiles are illustrative. The verified claim is software/physics-chain execution, not calibrated building performance.


### Engineering evidence receipts

Real ContamX execution is a software/physics-chain proof, not by itself engineering truth. Engineering readiness now requires typed, topology-bound evidence receipts in addition to `engineering_validated=true`.

The supported evidence types are:

```text
metric_geometry_measurement
airflow_calibration
boundary_measurement
prj_engineering_review
```

Issue a receipt from a raw field/calibration bundle:

```bash
python examples/issue_contam_evidence_receipt.py \
  examples/evidence/metric_geometry.bundle.example.json \
  --out artifacts/metric-geometry.receipt.json
```

The same pattern applies to the airflow, boundary, and PRJ-review examples under `examples/evidence/`.

Each receipt binds:

```text
evidence_id
evidence_type
topology_id
captured_at
method
source / instrument identity
typed summary
data SHA-256
receipt SHA-256
```

Profiles may carry these receipts in `evidence_receipts`. The engineering-readiness audit then requires the correct receipt type for each profile component and rejects receipts from a different topology.

```text
metric profile
  → metric_geometry_measurement receipt

airflow profile
  → airflow_calibration receipt
  → closed-window leakage calibration remains explicit

boundary profile
  → boundary_measurement receipt

PRJ serialization profile
  → prj_engineering_review receipt
```

A boolean `engineering_validated=true` with no matching receipt now remains `SOFTWARE_VERIFIED_ONLY`. Only topology-matched, typed evidence plus an accepted engineering evidence level can reach `ENGINEERING_READY`.


### Evidence → engineering profile compiler

Typed evidence receipts are now actionable inputs rather than passive audit metadata. The profile compiler turns validated raw evidence bundles into the existing CONTAM profile contracts without manually retyping field values.

```bash
# Full metric geometry overlay, including measured room volumes
python examples/compile_contam_profile.py metric \
  examples/evidence/metric_geometry.bundle.example.json \
  --out artifacts/metric-profile.json

# Airflow / leakage calibration profile
python examples/compile_contam_profile.py airflow \
  examples/evidence/airflow_calibration.bundle.example.json \
  --out artifacts/airflow-profile.json

# Weather + outdoor/initial CO2 boundary profile
python examples/compile_contam_profile.py boundary \
  examples/evidence/boundary_measurement.bundle.example.json \
  --out artifacts/boundary-profile.json
```

The compiler fails closed instead of inventing engineering assumptions:

- metric evidence must exactly cover all rooms, walls, and openings in the target topology;
- room volume is part of the metric evidence, not inherited silently from the demo layout;
- airflow calibration must cover every opening;
- multiple openings of the same kind must agree on the kind-level fit, because per-opening airflow rules are not yet supported;
- boundary evidence must contain a complete initial concentration for every modeled zone;
- the PRJ engineering review must approve the exact current profile SHA.

Bind a PRJ review to a concrete serialization profile:

```bash
python examples/compile_contam_profile.py review \
  examples/evidence/prj_engineering_review.bundle.example.json \
  --prj-profile examples/contam_prj_profile.example.json \
  --out artifacts/prj-profile.reviewed.json
```

The review bundle's `approved_profile_sha256` must match the current profile payload. Any later edit invalidates the old review binding.

The bundled evidence files remain examples with placeholder instrument/reviewer identities. They demonstrate the executable contract but are not field evidence for a real building.


### Evidence validity vs engineering approval

Issuing an evidence receipt proves that the bundle is structurally valid, typed, timestamped, source-bound, and hashable. It does **not** by itself mean that an engineer approved the evidence for production use.

For metric geometry, airflow calibration, and boundary measurements, engineering promotion requires an explicit approval block in the raw evidence bundle:

```json
{
  "approval": {
    "approved": true,
    "approved_by": "Engineer name",
    "approved_role": "HVAC / building-airflow engineer",
    "approved_at": "2026-10-06T14:30:00+08:00"
  }
}
```

Without that block, the evidence-backed profile remains `engineering_validated=false` and the final engineering-readiness audit fails closed. The final audit also re-checks receipt approval independently, so manually flipping the profile boolean cannot bypass the gate.

`prj_engineering_review` is the exception because the review receipt itself is the approval act and is additionally bound to the exact reviewed profile SHA.


### One-shot engineering CONTAM build

After the measurement/calibration bundles have explicit approval and the PRJ serialization profile has an exact engineering-review receipt, the full engineering-input pipeline can be executed with one command:

```bash
python examples/build_engineering_contam_project.py \
  --metric-evidence path/to/metric.bundle.json \
  --airflow-evidence path/to/airflow.bundle.json \
  --boundary-evidence path/to/boundary.bundle.json \
  --prj-profile path/to/contam-prj-profile.json \
  --prj-review-evidence path/to/prj-review.bundle.json \
  --out artifacts/engineering.prj \
  --receipt artifacts/engineering-build.json
```

The command performs:

```text
approved geometry evidence
→ measured metric overlay

approved airflow calibration
→ leakage-aware airflow profile

approved boundary observation
→ weather + CO2 boundary profile

exact PRJ review
→ reviewed serialization profile

all profiles
→ CONTAM IR
→ deterministic IDs
→ PRJ readiness
→ generated .prj
→ engineering evidence audit
```

A successful build returns:

```text
status = ENGINEERING_INPUTS_READY
engineering_inputs_ready = true
runtime_verified = false
engineering_truth = false
```

This distinction is intentional. The build proves that approved engineering inputs can be compiled consistently into a CONTAM project. A subsequent real ContamX execution is still required before runtime verification can be claimed.


### Engineering runtime verification

An `ENGINEERING_INPUTS_READY` build is still not a runtime claim. Verify the exact PRJ and exact build receipt through the shared CONTAM trajectory path:

```bash
python examples/verify_engineering_contam_runtime.py \
  artifacts/engineering.prj \
  artifacts/engineering-build.json \
  --steps 2 \
  --out artifacts/engineering-runtime.json
```

The verifier fails closed on:

- PRJ file SHA drift;
- topology or layout-contract drift;
- `DemoRuntimeSnapshot` drift;
- non-ready engineering build receipts;
- ContamX zone/path count drift;
- missing multi-window action coverage;
- incomplete solved CO₂ or path-flow observations.

A successful runtime receipt reports:

```text
status = ENGINEERING_RUNTIME_VERIFIED
engineering_inputs_ready = true
runtime_verified = true
engineering_model_verified = true
field_validation_verified = false
engineering_truth = false
```

The last two flags are deliberately separate. Real ContamX execution proves that the approved engineering model runs through the intended topology, controls, policy, and trajectory chain. It does **not** prove that model predictions match measured room behavior.

The evidence state machine is therefore:

```text
approved field/calibration evidence
→ ENGINEERING_INPUTS_READY
→ real ContamX runtime verification
→ ENGINEERING_RUNTIME_VERIFIED
→ prediction-vs-field validation (reserved)
→ engineering truth (not yet claimed)
```


### Prediction-vs-field validation

`ENGINEERING_RUNTIME_VERIFIED` proves that the approved model executes in the real CONTAM runtime. Final field validation is a separate gate and uses a protocol that must be approved **before** validation data are captured.

First freeze the validation protocol:

```bash
python examples/compile_field_validation_protocol.py \
  path/to/field-validation-protocol.json \
  --out artifacts/field-validation-protocol.frozen.json
```

The frozen protocol contains its deterministic `protocol_sha256`. It defines, before the field run:

- required topology;
- complete zone/opening coverage;
- minimum number of samples;
- per-zone CO₂ RMSE/MAE thresholds;
- opening-position MAE threshold;
- reviewer identity/role and approval time.

Then collect field measurements that reference both the exact protocol SHA and the exact engineering runtime receipt SHA:

```text
frozen protocol SHA
        +
ENGINEERING_RUNTIME_VERIFIED receipt SHA
        +
calibrated site sensor identity
        +
all runtime prediction steps
        ↓
field measurement bundle
```

Run validation:

```bash
python examples/validate_contam_against_field.py \
  artifacts/engineering-runtime.json \
  artifacts/field-validation-protocol.frozen.json \
  path/to/field-measurements.json \
  --out artifacts/field-validation.json \
  --require-pass
```

The validator fails closed when:

- the runtime receipt or prediction series hash has been altered;
- the field bundle references a stale protocol SHA;
- measurements were captured before protocol approval;
- the sensor source lacks model, serial, or calibration reference;
- any runtime prediction step is omitted;
- the measurement bundle tries to provide its own post-hoc thresholds;
- zone/opening coverage is incomplete.

A passing receipt reports:

```text
FIELD_VALIDATION_PASSED
engineering_inputs_ready = true
runtime_verified = true
engineering_model_verified = true
field_validation_verified = true
engineering_truth = true
```

Here `engineering_truth=true` is intentionally scoped: it means the model met the approved validation thresholds for this topology, these measured signals, and this tested operating window. It is not a claim of universal validity outside that scope.

Templates are provided at:

```text
examples/field_validation_protocol.template.json
examples/field_measurements.template.json
```

The protocol template is deliberately unapproved by default.


### Raw field capture → aligned validation samples

Field validation no longer requires manually authored `step=0/1/2` samples. The runtime receipt exposes an explicit simulated time axis, and the approved validation protocol freezes the alignment rules before data collection:

```json
{
  "alignment": {
    "sampling_interval_s": 60,
    "max_skew_s": 10,
    "aggregation": "nearest",
    "accepted_qualities": ["measured"]
  }
}
```

A site recorder can emit timestamped events instead:

```text
timestamp
signal_type = co2_ppm | opening_pct
target_id
value
unit
quality
```

Compile the raw capture:

```bash
python examples/compile_field_capture.py \
  artifacts/engineering-runtime.json \
  artifacts/field-validation-protocol.frozen.json \
  path/to/field-capture.json \
  --out artifacts/field-measurements.aligned.json
```

The compiler aligns each required zone/opening signal to the runtime receipt's `simulation_time_s` using only records inside the pre-approved skew window. Records with an unapproved quality label are ignored. A raw record cannot be consumed by more than one prediction point.

The generated bundle carries:

```text
raw_capture_sha256
alignment_receipt
alignment_sha256
selected record indices
expected timestamp
actual record timestamp
per-record skew
quality
```

Those hashes are then bound into the final field-validation receipt, preserving the chain:

```text
raw timestamped sensor events
→ approved deterministic alignment
→ validation samples
→ prediction-vs-field metrics
→ FIELD_VALIDATION_PASSED / FAILED
```

A starter capture contract is available at `examples/field_capture.template.json`.


### Import gateway logs from JSONL or CSV

Site systems do not need to emit the AirTrajectory capture envelope directly. Keep capture metadata in a small manifest JSON and export the actual measurements as JSONL/NDJSON or CSV with these columns:

```text
timestamp,signal_type,target_id,value,unit,quality
```

Import the raw files:

```bash
python examples/import_field_capture.py \
  path/to/capture.manifest.json \
  path/to/gateway.csv \
  --out artifacts/field-capture.json
```

For JSONL:

```bash
python examples/import_field_capture.py \
  path/to/capture.manifest.json \
  path/to/gateway.jsonl \
  --out artifacts/field-capture.json
```

The importer binds the original files with:

```text
manifest_sha256
records_sha256
record_count
records_format
import_receipt_sha256
```

Those hashes are preserved through capture alignment and into the final field-validation receipt, so a validation result can be traced back to the exact gateway export bytes.


### One-command field validation pipeline

The import, alignment, and validation stages can now be executed as one reproducible command:

```bash
python examples/run_field_validation_pipeline.py \
  artifacts/engineering-runtime.json \
  artifacts/field-validation-protocol.frozen.json \
  path/to/capture.manifest.json \
  path/to/gateway.csv \
  --out artifacts/field-validation-pipeline.json \
  --aligned-out artifacts/field-measurements.aligned.json \
  --require-pass
```

The same command accepts JSONL/NDJSON logs. The pipeline receipt binds:

```text
runtime receipt SHA
protocol SHA
source records SHA
import receipt SHA
raw capture SHA
alignment SHA
aligned bundle SHA
field validation receipt SHA
pipeline receipt SHA
```

Intermediate aligned samples are optional output for audit/debugging; they are not required for normal operation.


### Read-only WindowPilot field capture

AirTrajectory can now collect validation records directly from multiple WindowPilot runtimes without issuing actuator commands:

```bash
python examples/capture_windowpilot_field_data.py \
  artifacts/engineering-runtime.json \
  artifacts/field-validation-protocol.frozen.json \
  examples/windowpilot_endpoints.example.json \
  --validation-id site-run-001 \
  --out artifacts/windowpilot-field-capture.json
```

For the current fixed demo topology, the validation contract distinguishes:

```text
measured opening positions:
  W1 / W2 / W3

fixed topology assumptions:
  D1 = 100%
  D2 = 100%
```

Fixed doors remain part of topology completeness but are not fabricated as measured actuator evidence. Their declared values are checked against every runtime prediction step.

The WindowPilot adapter is read-only. It uses:

```text
driver.read_sensors()
→ measured CO2 + source timestamp + ThingModel/site provenance

driver.physical_readiness()
→ latest_position_feedback.measured=true
→ hardware_identity.identity_sha256
```

It fails closed when an endpoint is simulated, measured position is unavailable, CO2 lacks provenance, endpoint hardware identity changes during capture, or CO2 sources span multiple physical sites. The resulting capture carries a hashed `windowpilot_capture_provenance` that is preserved through alignment and into the final validation receipt.


### One-command WindowPilot field validation

The direct hardware path can now run as one read-only command:

```bash
python examples/run_windowpilot_field_validation.py \
  artifacts/engineering-runtime.json \
  artifacts/field-validation-protocol.frozen.json \
  examples/windowpilot_endpoints.example.json \
  --validation-id site-run-001 \
  --out artifacts/windowpilot-field-validation.json \
  --capture-out artifacts/windowpilot-field-capture.json \
  --aligned-out artifacts/windowpilot-field-aligned.json \
  --require-pass
```

This command performs:

```text
WindowPilot measured CO2 + measured position
→ multi-endpoint site / hardware identity checks
→ timestamped field-capture records
→ approved time alignment
→ prediction-vs-field metrics
→ FIELD_VALIDATION_PASSED / FAILED
```

The path is read-only: it never calls `set_position()` or WindowPilot actuator endpoints. Fixed openings such as D1/D2 remain declared topology assumptions and are checked against runtime predictions instead of being fabricated as measured records.


### WindowPilot validation preflight

Before waiting for a full field-validation capture, run a read-only preflight:

```bash
python examples/preflight_windowpilot_field_validation.py \
  artifacts/engineering-runtime.json \
  artifacts/field-validation-protocol.frozen.json \
  path/to/windowpilot-endpoints.json \
  --out artifacts/windowpilot-field-preflight.json
```

The preflight performs no actuator writes. It verifies, before sampling starts:

```text
runtime receipt / topology / layout match
approved protocol + sample-count compatibility
configured source metadata is no longer template placeholders
all configured WindowPilot endpoints are present
non-simulated execution
measured position capability
fresh measured position feedback
fresh CO2 in ppm
bounded clock skew
valid hardware identity
single physical site across CO2 sources
fixed-opening assumptions match the protocol
```

The default example config uses:

```json
{
  "max_sample_age_s": 10,
  "max_future_skew_s": 2
}
```

A successful preflight emits `status=PASS`, `actuator_writes=0`, endpoint identity/source summaries, and a deterministic `preflight_receipt_sha256`.

The one-command WindowPilot validation pipeline now requires this preflight to pass before it starts the timed sampling loop and binds the preflight receipt hash into the final pipeline receipt.


### WindowPilot contract compatibility probe

Before the first real hardware run, use the diagnostic probe to inspect the actual WindowPilot API contract without actuator writes:

```bash
python examples/probe_windowpilot_contract.py \
  path/to/windowpilot-endpoints.json \
  --out artifacts/windowpilot-contract-probe.json
```

For automation, require full compatibility:

```bash
python examples/probe_windowpilot_contract.py \
  path/to/windowpilot-endpoints.json \
  --out artifacts/windowpilot-contract-probe.json \
  --require-compatible
```

The probe performs only:

```text
GET /api/capabilities
GET /api/physical-readiness
GET /api/state
```

and classifies each endpoint as:

```text
COMPATIBLE
PARTIAL
INCOMPATIBLE
```

It reports exact findings such as:

```text
EXECUTION_BLOCK_MISSING
MEASURED_POSITION_CAPABILITY_MISSING
HARDWARE_IDENTITY_MISSING
POSITION_FEEDBACK_MISSING
CO2_VALUE_MISSING
CO2_TIMESTAMP_MISSING
CO2_EVIDENCE_MISSING
CO2_SITE_BINDING_MISSING
```

Each finding includes an adapter/action hint so the first real-hardware mismatch can be diagnosed instead of collapsing into one generic preflight error.

For privacy and operational safety, the report does not embed full raw endpoint payloads. It stores deterministic payload SHA-256 values and structural shapes plus only the minimum observed fields needed for compatibility diagnosis.

Use the stages separately:

```text
unknown real WindowPilot payload
→ contract probe
→ fix adapter/API contract if needed
→ validation preflight
→ timed field capture
→ field validation
```

Both the probe and preflight are read-only and issue zero actuator writes.


### Freeze and detect WindowPilot contract drift

After the first real WindowPilot configuration reaches `COMPATIBLE`, freeze that known-good contract as a baseline:

```bash
python examples/freeze_windowpilot_contract_baseline.py \
  artifacts/windowpilot-contract-probe.json \
  --baseline-id site-a-windowpilot-v1 \
  --out artifacts/windowpilot-contract-baseline.json
```

On later deployments or WindowPilot upgrades, probe again and compare before field-validation preflight:

```bash
python examples/compare_windowpilot_contract_baseline.py \
  artifacts/windowpilot-contract-baseline.json \
  artifacts/windowpilot-contract-probe.current.json \
  --out artifacts/windowpilot-contract-drift.json \
  --require-match
```

The baseline deliberately ignores dynamic measurement values, timestamps, and full payload SHA values. Normal CO₂ changes therefore do not create false drift.

It freezes two separate boundaries:

```text
CONTRACT
  endpoint JSON shapes
  simulated / measured_position semantics
  transport
  position-evidence field presence
  CO2 value / timestamp / evidence presence

INSTANCE
  endpoint URL fingerprint
  hardware identity SHA-256
  physical CO2 site_id
```

Comparison results are:

```text
MATCH
DRIFT
  ├─ CONTRACT_DRIFT
  └─ INSTANCE_DRIFT
```

A frozen baseline can only be created from a fully `COMPATIBLE` probe. Both the baseline and every compared probe are hash-verified before comparison.

Recommended real-site startup sequence:

```text
contract probe
→ baseline drift comparison
→ WindowPilot validation preflight
→ timed read-only field capture
→ prediction-vs-field validation
```


### Baseline-gated WindowPilot field validation

The one-command WindowPilot field-validation CLI can now enforce a frozen contract baseline before preflight and timed sampling.

```bash
python examples/run_windowpilot_field_validation.py \
  artifacts/engineering-runtime.json \
  artifacts/field-validation-protocol.frozen.json \
  path/to/windowpilot-endpoints.json \
  --validation-id site-run-001 \
  --contract-baseline artifacts/windowpilot-contract-baseline.json \
  --probe-out artifacts/windowpilot-contract-probe.current.json \
  --contract-check-out artifacts/windowpilot-contract-drift.json \
  --out artifacts/windowpilot-field-validation.json \
  --capture-out artifacts/windowpilot-field-capture.json \
  --aligned-out artifacts/windowpilot-field-aligned.json \
  --require-pass
```

When `--contract-baseline` is provided, the startup sequence is mandatory:

```text
live contract probe
→ frozen baseline comparison
→ MATCH required
→ WindowPilot validation preflight
→ timed read-only sampling
→ alignment
→ prediction-vs-field validation
```

A contract drift exits before preflight/sampling with a dedicated non-zero exit code. The core pipeline also recomputes the baseline comparison, so bypassing the CLI-side check cannot silently skip the gate.

A successful pipeline receipt binds:

```text
contract_baseline_sha256
contract_probe_receipt_sha256
contract_comparison_sha256
preflight_receipt_sha256
windowpilot_capture_sha256
alignment_sha256
field_validation_receipt_sha256
pipeline_receipt_sha256
```


### Replayable WindowPilot startup evidence bundle

After a real site completes the read-only startup gates, preserve the exact startup lineage as a portable bundle:

```text
frozen contract baseline
+ current contract probe
+ baseline comparison MATCH
+ validation preflight PASS
→ startup evidence bundle
```

Build it:

```bash
python examples/build_windowpilot_startup_bundle.py \
  artifacts/windowpilot-contract-baseline.json \
  artifacts/windowpilot-contract-probe.current.json \
  artifacts/windowpilot-contract-drift.json \
  artifacts/windowpilot-field-preflight.json \
  --bundle-id site-a-startup-001 \
  --out artifacts/windowpilot-startup-bundle.json
```

The builder independently replays the baseline comparison instead of trusting the supplied comparison artifact. It also requires:

```text
comparison status = MATCH
preflight status = PASS
preflight actuator_writes = 0
same endpoint set across baseline / probe / preflight
same hardware identity per endpoint
same physical site lineage
valid hashes on every source artifact
```

The resulting bundle contains only normalized identity/provenance summaries and source receipt hashes. It does not embed raw WindowPilot HTTP payloads.

Later, verify the startup evidence offline without contacting hardware:

```bash
python examples/verify_windowpilot_startup_bundle.py \
  artifacts/windowpilot-startup-bundle.json \
  artifacts/windowpilot-contract-baseline.json \
  artifacts/windowpilot-contract-probe.current.json \
  artifacts/windowpilot-contract-drift.json \
  artifacts/windowpilot-field-preflight.json \
  --out artifacts/windowpilot-startup-replay.json
```

Offline replay rebuilds the bundle from the four source artifacts and requires exact equality with the persisted bundle. Re-signing a modified comparison or preflight artifact is not sufficient if its cross-artifact lineage no longer matches.

Evidence boundary:

```text
VERIFIED_READ_ONLY_STARTUP
≠ physical tau0
≠ field-model accuracy
≠ FIELD_VALIDATION_PASSED
```

The bundle exists so the first real hardware contact can be carried into development and CI as reproducible evidence, without repeatedly reconnecting to the site merely to debug adapter/contract logic.


### Emit startup evidence during one-command validation

When a frozen contract baseline is already available, the one-command WindowPilot validation flow can now persist the startup evidence bundle from the exact preflight instance used before timed sampling:

```bash
python examples/run_windowpilot_field_validation.py \
  artifacts/engineering-runtime.json \
  artifacts/field-validation-protocol.frozen.json \
  path/to/windowpilot-endpoints.json \
  --validation-id site-run-001 \
  --contract-baseline artifacts/windowpilot-contract-baseline.json \
  --probe-out artifacts/windowpilot-contract-probe.current.json \
  --contract-check-out artifacts/windowpilot-contract-drift.json \
  --startup-bundle-id site-a-startup-001 \
  --startup-bundle-out artifacts/windowpilot-startup-bundle.json \
  --out artifacts/windowpilot-field-validation.json \
  --require-pass
```

The pipeline does not run a second preflight merely to build the bundle. The bundle is generated from the same preflight receipt that gates the subsequent timed sampling, and the final pipeline receipt binds `startup_bundle_sha256`.

Requesting a startup bundle without a contract baseline/current probe fails closed.


### Declarative WindowPilot contract mapping

If a real WindowPilot/vendor runtime exposes the right semantics under different JSON paths, adapt the response contract with a declarative mapping profile instead of changing AirTrajectory validation code.

A mapping profile can normalize only these read-only endpoints:

```text
GET /api/capabilities
GET /api/physical-readiness
GET /api/state
```

Example profile:

```text
examples/windowpilot_contract_mapping.example.json
```

Profiles are referenced from the endpoint configuration:

```json
{
  "contract_mapping_profiles": {
    "vendor-v1": {
      "...": "copy the validated mapping profile here"
    }
  },
  "windowpilot_endpoints": {
    "W1": {
      "base_url": "http://127.0.0.1:8101",
      "contract_mapping_profile": "vendor-v1"
    }
  }
}
```

The mapping DSL supports only:

```text
source JSON path
→ canonical JSON path
+ optional coercion: identity / string / float / int / bool
+ optional non-required/default behavior
```

There is no expression evaluation or executable transformation. Unmapped vendor fields are not copied into the canonical payload.

The same normalized mapping is used by:

```text
WindowPilotHTTPDriver
contract probe
preflight
field capture
validation
```

POST actuator requests are never transformed by the response mapping layer.

Every normalized profile receives a deterministic `profile_sha256`. The contract probe exposes the active `profile_id/profile_sha256`, and the frozen WindowPilot contract baseline includes that mapping identity. Changing the mapping profile therefore produces `CONTRACT_DRIFT` even when the resulting JSON shape happens to remain the same.

Recommended first-hardware workflow when the raw API shape differs:

```text
raw real payload
→ contract probe identifies mismatch
→ write/update mapping profile
→ probe canonicalized contract
→ COMPATIBLE
→ freeze baseline
→ preflight
→ startup bundle / timed field validation
```

A mapping profile only normalizes representation. It must not be used to manufacture missing measured evidence, hardware identity, timestamps, or site lineage.


### Offline mapping fixture evaluation

When the first real device payloads are available, save the three read-only GET responses and iterate on the mapping profile offline before returning to the site:

```bash
python examples/evaluate_windowpilot_mapping_fixture.py \
  examples/windowpilot_contract_mapping.example.json \
  captures/capabilities.json \
  captures/physical-readiness.json \
  captures/state.json \
  --fixture-id site-a-w1-first-contact \
  --report-out artifacts/windowpilot-mapping-evaluation.json \
  --canonical-out artifacts/windowpilot-canonical-payloads.json \
  --require-compatible
```

The evaluator performs no network requests and no actuator writes. It distinguishes:

```text
MAPPING_ERROR
  source path/coercion/profile problem

INCOMPATIBLE
  mapping succeeded, but canonical semantics still fail the WindowPilot contract

PARTIAL
  canonical contract has warnings only

COMPATIBLE
  mapped payload satisfies the compatibility probe
```

The report binds:

```text
mapping profile id / SHA
exact raw file SHA-256 per endpoint
canonical payload SHA-256 per endpoint
compatibility probe receipt SHA
evaluation SHA
```

Raw file hashes are calculated from the exact bytes, not normalized JSON. Two files with identical JSON semantics but different bytes therefore have different raw evidence hashes while producing the same canonical payload hash.

The evaluation report does not copy the raw vendor payload. Canonical payloads are written only when `--canonical-out` is requested.

Recommended first-contact loop:

```text
save real GET payloads once
→ offline mapping evaluation
→ edit mapping profile
→ COMPATIBLE
→ reconnect to site
→ live contract probe
→ freeze baseline
→ preflight
→ startup bundle / field validation
```


### First-contact WindowPilot raw capture

For the first real hardware contact, capture the exact bytes returned by the three read-only WindowPilot endpoints before iterating on mapping profiles:

```bash
export WINDOWPILOT_AUTH='Bearer ...'
export WINDOWPILOT_API_KEY='...'

python examples/capture_windowpilot_first_contact.py \
  path/to/windowpilot-endpoints.json \
  --out-dir artifacts/windowpilot-first-contact \
  --manifest-out artifacts/windowpilot-first-contact.json
```

Endpoint authentication is configured by environment-variable reference, not by placing secrets in repository JSON:

```json
{
  "windowpilot_endpoints": {
    "W1": {
      "base_url": "https://windowpilot.example",
      "headers_env": {
        "Authorization": "WINDOWPILOT_AUTH",
        "X-API-Key": "WINDOWPILOT_API_KEY"
      }
    }
  }
}
```

The config stores only environment-variable names. Runtime header values are resolved immediately before the HTTP request and are not written into the first-contact manifest.

The capture path is intentionally constrained to:

```text
GET /api/capabilities
GET /api/physical-readiness
GET /api/state
```

For each configured endpoint it writes:

```text
<out-dir>/<endpoint-id>/capabilities.json
<out-dir>/<endpoint-id>/physical_readiness.json
<out-dir>/<endpoint-id>/state.json
```

The manifest records only:

```text
base URL fingerprint
request header names (never values)
HTTP status
content type
exact response byte length
exact response SHA-256
endpoint capture SHA-256
aggregate first-contact SHA-256
network request count
actuator_writes = 0
```

Response bodies must be successful 2xx JSON objects. Missing auth environment variables, unsafe endpoint IDs, non-JSON responses, and non-success HTTP responses fail closed.

The captured files can be passed directly to the offline mapping evaluator:

```bash
python examples/evaluate_windowpilot_mapping_fixture.py \
  path/to/mapping-profile.json \
  artifacts/windowpilot-first-contact/W1/capabilities.json \
  artifacts/windowpilot-first-contact/W1/physical_readiness.json \
  artifacts/windowpilot-first-contact/W1/state.json \
  --fixture-id site-a-w1-first-contact \
  --report-out artifacts/windowpilot-mapping-evaluation.json \
  --canonical-out artifacts/windowpilot-canonical-payloads.json \
  --require-compatible
```

The same environment-backed HTTP header configuration is used by the live contract probe and WindowPilot drivers, so first-contact capture, live probe, preflight, and field validation do not diverge on authentication behavior.


### One-command WindowPilot first-contact workspace

For short hardware-access windows, capture the raw evidence and optionally evaluate a mapping profile in the same command:

```bash
python examples/build_windowpilot_first_contact_workspace.py \
  path/to/windowpilot-endpoints.json \
  --out-dir artifacts/windowpilot-first-contact \
  --workspace-out artifacts/windowpilot-first-contact-workspace.json \
  --mapping-profile path/to/windowpilot-mapping.json \
  --require-compatible
```

The workspace runs the real network capture exactly once. Each successful endpoint writes its three exact raw response files, and the optional mapping evaluation runs only against those saved bytes in memory.

Workspace status is explicit:

```text
CAPTURED_ONLY
CAPTURED_AND_COMPATIBLE
CAPTURED_WITH_MAPPING_ERROR
CAPTURED_WITH_INCOMPATIBLE_MAPPING
PARTIAL_CAPTURE
PARTIAL_CAPTURE_WITH_MAPPING
```

Mapping failure does not discard the first-contact raw capture. An invalid profile, missing source path, or canonical incompatibility is recorded as a mapping result while the exact device responses remain available for offline iteration.

Multi-endpoint capture is also failure-isolated. If W1 succeeds and W2 fails, the W1 payloads are preserved and the workspace records a `capture_errors` entry for W2. Because a failed endpoint may have issued an unknown number of GET attempts before the exception, partial workspaces do not fabricate an exact request count:

```text
successful_network_requests = known successful lower bound
network_requests_exact      = false
network_requests            = null
```

Only the all-success case reports an exact total.

Recommended short-site workflow:

```text
one command on site
→ preserve all successful raw endpoint captures
→ optional immediate mapping check
→ leave site with the workspace
→ iterate mapping offline
→ return only when live probe/preflight is ready
```


### Build a sanitized deployment config from first-contact evidence

After a first-contact workspace reaches compatible mapping, generate a deployment config draft instead of manually copying endpoint/auth/mapping settings:

```bash
python examples/build_windowpilot_deployment_config.py \
  path/to/original-windowpilot-config.json \
  artifacts/windowpilot-first-contact-workspace.json \
  --mapping-profile path/to/windowpilot-mapping.json \
  --mapping-profile-name vendor-v1 \
  --config-out artifacts/windowpilot-deployment.json \
  --receipt-out artifacts/windowpilot-deployment-draft.json \
  --require-ready
```

The builder only carries fields that can be justified from the source config and first-contact evidence:

```text
endpoint URL
timeout / feedback timeout / position tolerance
headers_env names (never secret values)
mapping profile reference + deterministic profile SHA
topology_id when already declared
fixed_openings when already declared
explicit field_capture source metadata
explicit room → CO2 endpoint mapping
```

It does not infer room identity from endpoint names. W1 does not automatically become `living`, and W2 does not automatically become `bedroom`.

The draft receipt reports:

```text
READY_FOR_LIVE_PROBE
DRAFT_WITH_BLOCKERS
```

Typical blockers include:

```text
endpoint mapping not COMPATIBLE
partial first-contact capture
replace-with-* deployment metadata
missing field_capture.source identity/calibration
missing explicit room-to-endpoint CO2 mapping
CO2 mapping references an endpoint not captured during first contact
mapping profile SHA differs from the profile evaluated in the workspace
```

The emitted config is sanitized by whitelist. Unknown endpoint fields, inline tokens, root passwords, private field-capture keys, and other arbitrary source-config keys are not copied. HTTP authentication remains represented only by `headers_env` variable names.

Recommended handoff:

```text
first-contact workspace
→ offline mapping COMPATIBLE
→ sanitized deployment config draft
→ READY_FOR_LIVE_PROBE
→ live contract probe
→ freeze baseline
→ preflight
→ startup bundle / field validation
```


### Real ContamX Independent vs Joint Golden Case

AirTrajectory now carries a fixed three-room transient strategy-comparison anchor:

```text
examples/golden_case.multispace_joint_v1.json
```

The Golden Case is bound to the current generated transient PRJ origin:

```text
living  = 1400 ppm
bedroom = 900 ppm
study   = 800 ppm
outdoor = 430 ppm

W1 = 65%
W2 = 35%
W3 = 55%
D1 = 100%
D2 = 100%

time step = 60 s
horizon   = 3 steps
```

The Independent reference is generated by the existing `MultiWindowRuleAgent` using only each exterior window's associated room CO₂. At this origin it produces:

```text
W1 → 75%
W2 → 35%
W3 → 0%
```

The Joint search evaluates that Independent reference together with coordinated W1/W2/W3 action vectors from the same origin, same transient PRJ, and same horizon.

Every real ContamX branch now exposes a complete per-zone CO₂ time series. The Golden Case scores:

```text
mean CO2
max CO2
mean excess above 1000 ppm
max excess above 1200 ppm
zone-steps above 1200 ppm
mean room-to-room CO2 imbalance
total opening movement
```

The CI receipt reports `WIN` or `TIE`; it does not force a Joint win. The Joint candidate pool includes the Independent reference, so the selected result must be non-regressive under the declared demo objective.

Run manually:

```bash
python examples/run_contam_joint_golden_case.py \
  artifacts/multispace-transient.prj \
  artifacts/multispace-transient.prj.json \
  --out artifacts/contam-joint-golden-case.json
```

Evidence boundary:

```text
real ContamX transient physics         ✅
same-origin Independent vs Joint       ✅
quantitative reproducible receipt      ✅
field-validated control advantage      ❌
engineering truth                      ❌
```

This Golden Case is a regression and strategy-comparison anchor. It must not be presented as measured building performance until the same policy comparison is tied to real WindowPilot/field evidence.
