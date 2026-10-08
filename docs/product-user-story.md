# AirTrajectory Product User Story

Status: product / research contract, not a claim that every capability below is already implemented.

## North star

AirTrajectory should answer one practical question:

> Given an arbitrary home layout, arbitrary door/window placement, current indoor/outdoor environmental state, and a user objective, what coordinated ventilation trajectory should the home execute next — and how should it replan from measured reality?

The product is not "an AI that opens windows." It is a topology-aware, physics-grounded trajectory system for multi-zone environmental improvement.

## Primary user story

As a home user, operator, or building integrator,

I want to provide my actual floor plan and current indoor/outdoor environmental state,

so that AirTrajectory can understand the home's room/door/window topology, search coordinated multi-window ventilation strategies, preview their expected effects on CO2, TVOC, formaldehyde, PM2.5, temperature, and humidity, execute a bounded strategy when authorized, and continuously replan from measured feedback.

I should not need to encode a fixed W1/W2/W3 topology by hand, and the system should expose uncertainty when critical geometry, source terms, or physical parameters are missing rather than invent engineering truth.

## Product loop

```text
IMPORT
  arbitrary floor plan / CAD / SVG / structured topology
      ↓
RECONSTRUCT
  rooms + walls + doors + windows + outdoor boundaries
      ↓
CORRECT
  user fixes recognition / geometry / connectivity
      ↓
OBSERVE
  indoor + outdoor environmental state
      ↓
SET OBJECTIVE
  improve air while respecting comfort / safety / energy constraints
      ↓
SEARCH
  topology-derived ventilation paths + coordinated opening actions
      ↓
SIMULATE
  fast model / CONTAM / higher-fidelity backend
      ↓
COMPARE
  predicted multi-objective trajectories
      ↓
EXECUTE
  bounded WindowPilot / BMS / device adapter action
      ↓
READ BACK
  measured opening state + fresh environmental observations
      ↓
RECONCILE
  prediction vs reality / confirmed vs unresolved effect
      ↓
REPLAN
  measured state becomes next physical origin
      ↓
LEARN
  append trajectory to reusable dataset / benchmark corpus
```

The loop repeats. Reality, not the model, defines the next trusted origin.

## Core research hypothesis — trajectory-driven agent post-training

AirTrajectory is not complete if it only asks an agent or controller to make a fresh one-step decision from the current state.

The central falsifiable hypothesis is:

> A decision system post-trained on topology-aware ventilation trajectories, and then refined through simulated / counterfactual interaction, should make better coordinated multi-window decisions than an otherwise comparable agent that judges each window or each state independently.

This hypothesis is **not yet proven by the current repository**.

The intended learning loop is:

```text
Rule / expert trajectories
+ CONTAM / fast-model counterfactual trajectories
+ safe exploration trajectories
+ measured physical trajectories
        ↓
trajectory dataset
        ↓
behavior cloning / supervised post-training
        ↓
offline RL / value or ranking refinement
        ↓
simulator interaction fine-tuning where justified
        ↓
topology-conditioned decision policy / candidate ranker
        ↓
held-out topology evaluation
        ↓
bounded physical deployment
        ↓
measured outcomes return to the dataset
```

The learned component may be a compact policy, value/ranking model, graph-conditioned controller, or a post-trained agent model. The durable asset is the trajectory/evidence corpus and benchmark contract, not one checkpoint.

The agent must not directly improvise actuator percentages without topology, physics, safety, and benchmark constraints.

### Falsification test

At minimum compare, from the same origin and horizon:

1. independent / one-window-at-a-time judgment;
2. deterministic joint rule;
3. agent without trajectory post-training;
4. behavior-cloned / supervised-post-trained policy;
5. offline-RL or interaction-refined policy when available.

The post-training hypothesis is supported only if the learned system improves meaningful environmental outcomes on held-out topology families **without safety regression**.

If it does not outperform simpler baselines, the project must report that result and reduce the role of learning rather than preserve the hypothesis by changing the story.

## Story 1 — Import any home

### User intent

"I want to use my own home, not a hard-coded demo layout."

### Input

At least one of:

- raster floor plan;
- CAD / SVG;
- existing 3D scene export;
- structured room/door/window JSON.

### System behavior

The system should reconstruct:

- rooms / zones;
- walls;
- indoor doors and other internal openings;
- exterior windows / vents;
- connectivity;
- opening placement along a wall;
- orientation when available;
- metric dimensions when available.

### Human correction

The user must be able to:

- add / remove / rename rooms;
- split / merge zones;
- add / remove / move doors and windows;
- change opening dimensions and orientation;
- correct indoor/outdoor connectivity.

### Acceptance boundary

Automatic recognition is not required to be perfect.

Success means:

> any supported source can be corrected into one canonical topology contract without rewriting the downstream control system.

Missing physical geometry must remain explicit. The system must not silently fabricate engineering-grade dimensions.

## Story 2 — Represent arbitrary room / door / window counts

### User intent

"My home should not stop working because it has five rooms or seven windows."

### System behavior

The runtime must avoid fixed-size assumptions such as:

```text
state = [room1, room2, room3]
action = [W1, W2, W3]
```

and instead operate over variable topology:

```text
Zones V
Openings E
State attached to V/E
Candidate ventilation paths P(V,E)
Action set derived from available controllable openings
```

### Acceptance boundary

A new topology should enter through the same topology contract and trajectory interfaces.

No core control semantic should require source-code changes solely because room/window count changes.

## Story 3 — Build the environmental world state

### User intent

"Show me what is wrong with the air now."

### Indoor state by zone

The target state model supports:

- CO2;
- TVOC;
- formaldehyde / HCHO;
- PM2.5;
- temperature;
- relative humidity;
- occupancy / source terms where available.

### Outdoor state

The target boundary model supports:

- PM2.5 / pollutant concentration;
- temperature;
- humidity;
- wind speed;
- wind direction;
- rain;
- optional pressure / weather fields required by the physics backend.

### Evidence classes

Every value must carry enough provenance to distinguish, where applicable:

- measured;
- estimated;
- simulated;
- stale;
- unavailable.

The planner may use estimates with bounded confidence; it must not relabel them as measurements.

## Story 4 — Express goals, not raw actuator commands

### User intent

Examples:

- "Improve the bedroom air before sleep."
- "Reduce formaldehyde without making the room too cold."
- "Keep the whole home fresh while outdoor PM2.5 is high."
- "Optimize automatically."

### Objective model

The system translates user intent into a multi-objective target over:

- pollutant exposure / concentration;
- thermal comfort;
- humidity comfort;
- energy / heat-loss proxy;
- actuator movement;
- rain / safety constraints;
- optional noise / privacy constraints.

### Acceptance boundary

The user objective should be inspectable.

The system should be able to explain which objectives conflict instead of hiding all trade-offs behind one opaque scalar reward.

## Story 5 — Generate topology-aware coordinated ventilation strategies

### User intent

"Choose the windows as a system, not one by one."

### System behavior

The planner should derive candidate strategies from the current topology, including:

- individual-opening actions;
- opening groups;
- cross-ventilation pairs;
- topology-derived ventilation paths;
- hold / no-action baseline.

Example:

```text
outside → living W1 → corridor D1 → bedroom D2 → bedroom W4 → outside
```

may yield a coordinated action such as:

```text
W1 = 30%
W2 = 0%
W3 = 15%
W4 = 50%
```

### Baselines

Every claim of improvement should be comparable against at least:

- HOLD / do nothing;
- independent per-window control;
- a deterministic rule baseline.

Learning-based policies are additions, not substitutes for these baselines.

## Story 6 — Preview multiple futures

### User intent

"What happens if I choose this strategy?"

### System behavior

From one immutable origin, evaluate several candidate futures.

For each candidate, show predicted changes such as:

- CO2 trajectory;
- TVOC trajectory;
- HCHO trajectory;
- PM2.5 trajectory;
- temperature;
- humidity;
- opening movement;
- constraint violations;
- confidence / physics provenance.

### Product principle

The user sees consequences, not just commands.

```text
same origin
  ├─ strategy A
  ├─ strategy B
  ├─ strategy C
  └─ HOLD
```

Comparisons must use the same origin and horizon.

## Story 7 — Handle conflicting environmental goals

### Example

Indoor CO2 and HCHO are high, but outdoor PM2.5 is also high.

A naive system says:

```text
CO2 high → open windows
```

AirTrajectory must be able to say:

```text
large ventilation would reduce CO2 / HCHO
but increase PM2.5 exposure

candidate:
  short bounded cross-flow
  lower opening percentage
  limited duration
  re-observe after N minutes
```

### Acceptance boundary

The system is allowed to recommend HOLD or a smaller intervention.

"More ventilation" is not automatically better.

## Story 8 — Execute conservatively in the real world

### User intent

"Apply the chosen strategy to my actual windows."

### Runtime sequence

```text
measured physical origin
→ fresh authorization / safety check
→ bounded command
→ device acknowledgement
→ measured actuator readback
→ fresh post-action environmental observation
→ reconciled next physical origin
```

### Acceptance boundary

A transport ACK is not physical proof.

If the outcome is unresolved, the system must remain unresolved rather than blindly retrying or fabricating the next state.

## Story 9 — Replan when the world changes

### Replan triggers

Examples:

- rain begins;
- wind changes;
- a user manually moves a window;
- a door opens / closes;
- occupancy changes;
- outdoor PM2.5 rises;
- sensor evidence becomes stale;
- actual actuator position differs from prediction.

### Product behavior

The current trajectory becomes stale when its origin assumptions are no longer valid.

The system should:

```text
invalidate old continuation
→ capture current state
→ rerun candidate search / physics
→ issue a new trajectory
```

## Story 10 — Learn from prediction error

### User intent

"Get better at my home without requiring a full retraining project."

For every executed trajectory:

```text
topology
+ origin state
+ objective
+ proposed joint action
+ predicted future
+ executed action
+ measured future
+ prediction error
+ reward / outcome
```

is preserved as training and calibration material.

### Learning targets

The system may improve:

- local physical calibration;
- candidate ranking;
- topology-conditioned policy;
- uncertainty estimates;
- sim-to-real correction.

The model remains replaceable; the trajectory/evidence corpus is durable.

## Story 11 — Generalize to a never-seen topology

### User intent

"I uploaded a home the system has never seen before. It should still work."

### Required transfer

The system should not depend on memorized fixed device IDs or fixed room counts.

It should reconstruct:

```text
new floor plan
→ canonical topology
→ candidate ventilation paths
→ physics evaluation
→ coordinated actions
```

### Generalization ladder

1. **Parameter generalization**
   - new geometry / weather / occupancy on known topology families.

2. **Scale generalization**
   - new room / door / window counts.

3. **Structural generalization**
   - unseen chain / branch / hub / irregular connectivity.

4. **Environmental generalization**
   - different pollutant / comfort trade-offs.

5. **Device generalization**
   - different actuators and feedback contracts behind adapters.

6. **Sim-to-real generalization**
   - simulated / CONTAM policy transferred to a measured physical origin.

## Story 12 — Give researchers a reproducible benchmark

### Researcher intent

"I want to test whether my policy actually generalizes."

A benchmark episode must bind:

- topology identity;
- environmental origin;
- objective;
- candidate/action space;
- physics backend;
- horizon;
- outcome metrics;
- provenance;
- trajectory.

### Minimum comparisons

- HOLD;
- independent control;
- deterministic joint rule;
- learned policy.

### Core outcome metrics

At minimum where applicable:

- pollutant AUC;
- peak / mean / worst-zone concentration;
- time above threshold;
- time to safe;
- temperature / humidity discomfort;
- actuator movement;
- safety violations;
- predicted-vs-real error.

No single reward number is sufficient as the only published result.

## Story 13 — Let a third party reuse the infrastructure without adopting the product

This is the infrastructure position.

A third party should eventually be able to reuse independently:

1. **Topology Contract**
   - arbitrary rooms / walls / doors / windows.

2. **Environmental State Contract**
   - multi-pollutant + comfort + provenance.

3. **Trajectory Contract**
   - origin → coordinated action → future / measured outcome.

4. **Physics Adapter Contract**
   - fast model / CONTAM / CFD / other solver.

5. **Policy Benchmark Contract**
   - HOLD / Independent / Joint / learned comparison.

6. **Physical Adapter Contract**
   - WindowPilot / BMS / other actuator runtime.

The long-term identity asset is not one model checkpoint.

It is the interoperable path:

```text
Floorplan
→ Topology
→ Environment
→ Candidate Paths
→ Physics
→ Trajectory
→ Physical Feedback
```

If another project can adopt one contract without adopting all of AirTrajectory,
that is stronger evidence of infrastructure value than another internal demo.

## Story 14 — Post-train the decision system from trajectories

### User / operator intent

"I want the system to become better at coordinated ventilation from accumulated experience instead of making every decision from scratch."

### Required behavior

Training data may come from:

- deterministic rule / expert demonstrations;
- CONTAM and other physics-backed rollouts;
- counterfactual branches from the same origin;
- safe randomized exploration in simulation;
- measured physical trajectories;
- intervention / override / failure trajectories.

Each training sample must remain bound to:

- topology identity;
- environmental origin;
- user objective;
- proposed and executed joint actions;
- safety intervention;
- predicted consequence;
- measured / simulated consequence;
- provenance / physics backend.

### Training ladder

The intended progression is:

```text
Rule demonstrations
→ BC / supervised post-training
→ Offline RL / value-ranker refinement
→ simulator interaction refinement
→ shadow evaluation
→ bounded physical execution
→ measured feedback
```

The exact algorithm is replaceable.

Current dependency-light BC / Offline-Q implementations count only as **learning-plumbing evidence** until they are evaluated on realistic joint action spaces and held-out structural topology families.

### Acceptance boundary

The project must publish an ablation that separates:

- topology-aware joint planning itself;
- physics/counterfactual search;
- trajectory post-training;
- additional RL refinement.

A learning claim passes only when the post-trained system beats the relevant simpler baseline on at least one meaningful environmental metric while:

- using the same origin / horizon;
- keeping safety non-regressive;
- not relying on exact training replay;
- reporting failures and negative results.

## Story 15 — Provide a playable truth-seeking exploration lab

### User intent

"I want to play with different homes, windows, weather, goals, and policies and see what the system actually thinks will happen."

The final public demo is not a decorative UI. It is an interactive experiment surface over real backend artifacts.

### Required interactions

The user should be able to:

- switch among multiple topologies, including a held-out topology;
- import / load a topology artifact;
- correct at least opening placement / state, and eventually room/opening structure;
- open / close multiple windows and doors;
- set environmental state and user objective;
- choose or compare policy modes:
  - HOLD;
  - Independent;
  - Rule Joint;
  - untrained / non-post-trained agent where applicable;
  - BC / supervised post-trained;
  - Offline RL / refined policy;
- fork one immutable origin into several futures;
- play / pause / scrub trajectories;
- inspect why a joint action was selected;
- trigger a world change such as rain / manual opening and watch the trajectory invalidate and replan.

### Visual truth surface

The lab should make visible:

- room / opening topology;
- active VentilationPath(s);
- opening percentages through time;
- CO2 / PM2.5 / temperature / humidity trajectories;
- airflow direction / vector field where produced by a physics backend;
- particle / streamline visualization only when its provenance is explicit;
- dead zones / low-flow regions where supported;
- policy / checkpoint identity;
- training-data / post-training provenance;
- simulator / physics source;
- safety interventions;
- predicted vs measured outcome.

No qualitative browser flow proxy may be presented as engineering airflow truth.

### Acceptance boundary

A visitor must be able to answer, without reading the source code:

1. what home/topology is being controlled?
2. what is the current environmental problem and user goal?
3. what alternatives were considered?
4. what did the non-learned baselines do?
5. what changed after trajectory post-training?
6. which coordinated windows/path did the policy choose?
7. what did the physics backend predict?
8. what actually happened, when physical evidence exists?
9. when reality changed, did the old plan become stale and replan?

The UI is complete only when it reveals these comparisons; animation alone is not completion.

## Non-goals

AirTrajectory should not become:

- a generic agent platform;
- a generic analytics system;
- a generic PPEP product;
- a UI-first smart-home demo;
- an LLM that directly improvises actuator percentages without physics / safety checks.

Correctness / evidence work exists to make physical trajectories trustworthy.
It does not replace the ventilation-control product.

## Product acceptance ladder

### A. Research MVP

- multi-room / multi-window topology;
- real CONTAM execution;
- joint strategy;
- HOLD / Independent baselines;
- trajectory generation;
- closed-loop replanning;
- unseen-topology benchmark.

### B. Arbitrary-layout MVP

- import or construct a previously unseen floor plan;
- correct it interactively;
- generate the canonical topology without code changes;
- derive variable-size candidate actions;
- run the same planning pipeline.

### C. Multi-environment MVP

At least CO2 + temperature + humidity + PM2.5 participate in one objective and
candidate comparison.

TVOC / HCHO enter only when source / emission assumptions are explicit enough
to make the result meaningful.

### D. Physical MVP

At least one real window / room completes:

```text
measured origin
→ planned coordinated action
→ physical execution
→ measured readback
→ next physical origin
→ replan
```

### E. Generalization result

Publish a held-out evaluation where:

- the test topology family is absent from training;
- exact training replay does not explain the result;
- Joint / learned control is compared against HOLD and Independent;
- safety does not regress;
- at least one meaningful environmental metric improves.

### F. Infrastructure signal

At least one independent third party:

- imports a contract;
- runs a benchmark;
- reproduces a trajectory;
- requests compatibility;
- or keeps an AirTrajectory-derived test / adapter in its own repository.

This is the first credible transition from proof-of-work to proof-of-position.

### G. Post-training result

Publish a same-origin ablation showing:

- independent / one-step baseline;
- deterministic Joint;
- non-post-trained agent where applicable;
- BC / supervised post-training;
- offline-RL / interaction-refined policy where available.

The learned system is not considered better unless it improves a meaningful held-out-topology outcome without safety regression.

Current toy BC / Offline-Q plumbing does not by itself satisfy this gate.

### H. Playable exploration proof

Publish an interactive lab where a visitor can:

- change topology / opening state / objective;
- compare HOLD / Independent / Joint / learned policies;
- fork and replay futures;
- see active VentilationPath and environmental trajectories;
- distinguish toy / CONTAM / CFD / physical provenance;
- trigger a world change and observe invalidation / replan.

The lab must render backend evidence rather than inventing an airflow story in the browser.

## One-sentence product story

> Give AirTrajectory any home topology and current environmental state; it constructs physics-grounded multi-window trajectories, uses accumulated simulated and measured trajectories to post-train a topology-aware decision system, compares learned decisions against non-learned baselines, exposes the alternatives in a playable exploration lab, executes conservatively on real devices, and keeps replanning from measured reality on homes it has never seen before.
