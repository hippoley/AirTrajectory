# Evidence / Coverage Semantics — Standards and Prior-Art Lineage

This document exists to keep AirTrajectory's long-horizon identity claim narrow,
portable, and attribution-safe.

The goal is not to claim ownership of coverage accounting. The goal is to show
where AirTrajectory contributes reusable executable boundary cases, how those
cases map into external systems, and which ideas clearly predate this work.

## Core boundary

```text
committed examined/test population
        ↓
executed / examined members
        ↓
evidence
        ↓
claim

coverage over that committed set
!=
proof that the source population itself was complete
```

AirTrajectory's durable contribution is the executable treatment of adjacent
failure cases and the cross-system reconciliation work, not the invention of
coverage accounting.

## Standards / ecosystem lineage

### CAP-1 — Coverage Attestation Profile

Source:
`draft-hillier-coverage-attestation-00` by Joel D. Hillier / Certisyn.

Status at review time:
- Active individual IETF Internet-Draft;
- not an adopted IETF standard;
- explicitly scoped to coverage accounting and internal consistency of stated
  bounds;
- explicitly does not establish producer truthfulness.

CAP-1 predates the current AirTrajectory coverage work and must be credited as
prior art for denominator, strata, unexamined-unit accounting, and bounded
absence claims.

### EMILIA CAP-1 composition

EMILIA adds a relying-party composition around CAP-1:

- verifier-owned eligible/examined-set commitments;
- one result binding per examined unit;
- eligible/examined roots and counts;
- CAP-1 digest bound as `census_digest`;
- signed coverage-reconciliation attestation;
- explicit nonclaims for `source_population_completeness` and
  `honest_enumeration`.

This independently encodes the same critical boundary:

```text
examined-set coverage
!=
source-population completeness
```

### Rul1an / cap1-conforming-but-misleading

Rul1an's adversarial work predates this lineage document and provides a stronger
relying-party analysis than AirTrajectory's narrower path.

Especially important prior art:

- C5 population-pin reasoning;
- conforming-but-misleading CAP-1 documents;
- explicit relying-party rules that separate internal CAP-1 conformance from
  claims a consumer may safely rely on.

AirTrajectory must not restate those findings as novel.

### Veklom VCGB / EEE

The Veklom review resolved an apparent gap through existing layering:

```text
VCGB
  canonical scenario population
  suite_hash
  harness-owned intents
  complete result bundle
        ↓
EEE
  per-execution evidence integrity
```

This showed that a new expected-population object did not belong in EEE.
The result was architectural subtraction, not extension.

### OpenTelemetry GenAI durable-runtime semantics

AirTrajectory contributed a sanitized physical-effect reference scenario to the
discussion around durable agent runtime observability:

```text
mutating effect intent
→ dispatch
→ ACK lost
→ effect unresolved
→ authoritative readback
→ bounded compensation
→ verified compensation
→ fresh measured post-state
```

The reusable distinction is adjacent to coverage semantics:

```text
transport / dispatch evidence
!=
authoritative effect evidence
```

This is not a proposed OpenTelemetry schema. It is a reference case for testing
generic external-effect semantics.

## AirTrajectory's own portable contributions

The current portable artifacts are:

- `test-vectors/conformance-coverage-v0.1.json`
- `interop/emilia/native-coverage-crosswalk-v0.1.json`
- `interop/emilia/cap1-coverage-layer-resolution-v0.1.json`
- `interop/veklom/vcgb-eee-layering-resolution-v0.1.json`
- `interop/opentelemetry/physical-effect-lost-ack-v0.1.json`

The durable semantic distinctions include:

```text
valid included evidence != complete expected coverage

NOT_SATISFIED != MISSING

transport failure != effect failure

compensation requested != compensation verified

closed examined-set coverage != source-population completeness
```

## Attribution boundary

AirTrajectory does **not** claim:

- invention of coverage accounting;
- authorship of CAP-1;
- authorship of EMILIA's coverage-composition semantics;
- authorship of Veklom EEE / VCGB;
- OpenTelemetry adoption of AirTrajectory semantics;
- IETF endorsement of any AirTrajectory artifact.

The identity claim supported by current evidence is narrower:

**cross-system evidence / coverage boundary semantics contributor**

## Long-horizon identity test

This lineage should still be useful if any one repository disappears.

A future reviewer should be able to verify three things:

1. AirTrajectory produced executable, portable boundary cases.
2. Those cases were tested against multiple independent external systems and
   corrected when prior art or better native layering already existed.
3. The work consistently preferred attribution, reuse of existing primitives,
   and architectural subtraction over claiming novelty.

That is the intended 5–10 year credential: not ownership of one schema, but a
public record of repeatedly locating and clarifying evidence / coverage
boundaries across evolving standards ecosystems.
