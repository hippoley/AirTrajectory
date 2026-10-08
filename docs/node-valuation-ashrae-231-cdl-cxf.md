# Node Valuation: ASHRAE 231 / CDL / CXF

Date: 2026-10-08

## Finding

ANSI/ASHRAE Standard 231-2026 is a newly published standard for a
vendor-independent, human- and machine-readable Control Description Language
(CDL) for building environmental control sequences. Its scope includes
mechanical systems, active facades, and lighting.

CXF is the JSON-LD exchange representation intended to move a specifically
configured CDL logic into/out of building automation systems.

This is highly adjacent to AirTrajectory, but it does **not** replace the
project's core problem.

## Boundary

AirTrajectory currently aims to own:

```text
measured environmental state
→ topology-aware candidate futures
→ multi-objective decision
→ bounded physical action
→ measured outcome
→ replan
```

CDL/CXF aims to own:

```text
declared control sequence
→ vendor-independent representation
→ simulation / translation
→ BAS implementation
```

The durable integration opportunity is therefore:

```text
AirTrajectory planner / optimizer
        ↓
declared execution envelope / fallback / safety sequence
        ↓
CDL / CXF
        ↓
BAS / active facade controller
```

## Why this node is higher-value than more IFC schema work

- Standard 231 became an ANSI/ASHRAE standard in 2026.
- Its stated scope explicitly covers active facades.
- CXF already defines a JSON-LD interchange surface for commercial control systems.
- The OpenBuildingControl toolchain and Modelica Buildings Library provide an
  executable reference ecosystem.
- A 2026 Automation in Construction paper already demonstrates BIM + Brick +
  CDL integration on a ventilation system, showing real research/industry pull.

## What AirTrajectory should NOT do

- Do not invent a competing control-sequence language.
- Do not serialize a one-off trajectory and call it CDL/CXF.
- Do not claim dynamic optimization is natively representable as a fixed CDL
  sequence without proving the mapping.
- Do not divert the project before multi-environment decision quality is real.

## Three integration hypotheses

### H1 — CDL safety/execution shell

Represent deterministic interlocks and fallback behavior in CDL/CXF while
AirTrajectory supplies bounded setpoints.

Examples:
- rain close;
- stale sensor fail-safe;
- maximum opening ramp;
- manual override priority;
- fallback HOLD.

This is the strongest near-term fit because these behaviors are deterministic,
portable, and should survive model replacement.

### H2 — Planner as ExtensionBlock / FMU

Explore whether a dynamic AirTrajectory planner can be packaged behind the
extension mechanism supported by the OpenBuildingControl ecosystem.

This is research-only until the execution and timing semantics are verified.

### H3 — AirTrajectory-generated sequence candidates

Generate fixed control sequences only for policies that can be expressed as
stable block logic. This may be useful for learned-policy distillation, but
must not be used to misrepresent an adaptive planner.

## Promotion gate

Promote ASHRAE 231/CDL/CXF to a first-class project integration only when at
least one is true:

1. a real AirTrajectory safety/fallback sequence is exported and simulated in
   the OpenBuildingControl / Modelica ecosystem;
2. a BAS-oriented user requests a portable control-sequence artifact;
3. a 231/CDL contributor or downstream tool engages with the integration;
4. the integration directly shortens the path to real active-facade deployment.

Until then, this is a high-value adjacent node, not the project's new identity.
