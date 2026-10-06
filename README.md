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
