# GEISA field-tool and conformance mapping note

> Status: exploratory, non-normative, and not an official GEISA artifact.
>
> Purpose: map field-control execution semantics that are already implemented
> and tested in AirTrajectory/WindowPilot to open questions in the GEISA
> specification and conformance repositories.

## Why this note exists

Grid-edge field tooling is a boundary between software intent and physical
infrastructure. At that boundary, a useful interoperability contract needs to
say more than "the API returned success."

The minimum useful model separates:

```text
observe
→ evaluate readiness
→ explicitly authorize mutation
→ issue a uniquely identified command
→ acknowledge command acceptance
→ observe measured target state
→ capture fresh environmental/device evidence
→ recover safely if the outcome is uncertain
→ persist evidence that can be independently re-verified
```

This note records one tested implementation of those semantics and proposes a
transport-neutral mapping to current GEISA discussions.

## Relevant GEISA discussions

The following open GEISA issues are particularly close to this boundary:

- `geisa/specification#110` — Cover basic field tool behaviors
- `geisa/specification#113` — Acknowledgement and/or credit to apps for messages
- `geisa/conformance#21` — Log test execution
- `geisa/conformance#37` — Test tool XML output needs a schema

This note does **not** claim that the requirements below are already GEISA
requirements. It is intended as implementation evidence and material that can
be refined into testable specification language if useful to the project.

## Proposed minimal field-tool behavior model

### FT-1 — Observe-only by default

Connecting a field tool and reading platform/device state should not implicitly
mutate the target.

**Testable observation**

- zero actuator/device writes occur during readiness inspection;
- target identity and measured state can be read before execution.

### FT-2 — Explicit mutation boundary

A state-changing operation should cross a separate, explicit execution boundary
after preconditions/readiness are evaluated.

**Testable observation**

- read-only preview and execute mode are distinguishable;
- execution cannot occur merely because a target is reachable.

### FT-3 — Stable target identity

Readiness, command acceptance, feedback, and recovery evidence should remain
bound to the same physical/platform identity.

**Testable observation**

- a target identity is present before mutation;
- a different identity at command or feedback time fails closed.

### FT-4 — Request identity and replay safety

Mutating requests should carry a unique client request identity and be
idempotent at the execution boundary.

**Testable observation**

- replay of a completed request does not execute the mutation twice;
- reuse of the same request identity with a different command is rejected;
- an uncertain outcome is not automatically replayed.

### FT-5 — Acknowledgement is not measured feedback

A command acknowledgement proves that an execution boundary accepted a request;
it does not prove that the physical target reached the requested state.

**Testable observation**

- command acknowledgement and measured target-state feedback are distinct
  evidence records;
- conformance can fail when acknowledgement succeeds but the measured state does
  not meet the expected condition.

### FT-6 — Fresh post-action observation

Evidence used for the next control decision should be newer than the command
and actuator feedback that caused the transition.

**Testable observation**

- stale target/environment readings cannot become a new control origin;
- timestamps are monotonic across request → acknowledgement → measured feedback
  → post-action observation.

### FT-7 — Uncertain-outcome recovery

After process failure, transport loss, or ambiguous hardware outcome, recovery
should re-observe the current physical state before another mutation is
authorized.

**Testable observation**

- uncertain/in-flight execution is not silently treated as completed;
- stale intent cannot be replayed solely because the original process died;
- recovery emits a new observation-derived origin.

### FT-8 — Persisted execution evidence

Field operations should leave enough structured evidence for an independent
verifier to reconstruct the transition.

A minimal record should answer:

- which test/operation ran;
- which target/platform identity it addressed;
- what readiness/preconditions passed;
- what request was authorized;
- whether the command was accepted;
- what state was measured afterward;
- whether evidence was fresh;
- whether recovery was required;
- whether the full transition independently verifies.

## Conformance evidence model

For `geisa/conformance#21`, free-form logging is useful for humans, but a
structured execution record enables deterministic post-run analysis.

A transport-neutral record could contain:

```text
execution_id
parent_execution_id
test_case_id
spec_clause_ref
target_identity
phase = PRECHECK | EXECUTE | OBSERVE | VERIFY | RECOVERY
started_at
completed_at
request_id
expected_observation
actual_observation
result = PASS | FAIL | BLOCKED | UNCERTAIN
reason_code
detail
artifact_refs[]
```

For `geisa/conformance#37`, XML can be one serialization of that model rather
than becoming the semantic model itself.

The important distinction is:

```text
semantic execution record
        ↓
XML / JSON / console rendering
```

rather than deriving semantics from today's log output shape.

## Implementation evidence in AirTrajectory / WindowPilot

The implementation below is deliberately more specific than the proposed GEISA
model. It is useful as a testbed, not as a requirement that GEISA copy the same
protocol.

### Zero-motion readiness

WindowPilot exposes read-only physical readiness. Real writes remain blocked
unless the physical backend, durable command-idempotency ledger, and stable
ledger scope are ready.

### Durable request identity

WindowPilot hardware writes require:

```text
command_ack_contract = windowpilot-command-ack-v2
command_idempotency_contract = durable-request-ledger-v1
command_idempotency_scope_id = <stable UUID>
```

Request IDs survive gateway restart through a durable ledger. Request records
are bound to the immutable ledger scope.

### Command acknowledgement vs feedback

A command acknowledgement is persisted separately from measured actuator
feedback. AirTrajectory does not treat an accepted command as physical state.

### Recovery and replay boundaries

AirTrajectory consumes a physical-origin receipt through a durable single-use
execution lease. A failed post-claim execution becomes
`RECOVERY_REQUIRED`; recovery is read-only and produces a fresh
observation-derived physical origin instead of reopening the old one.

### Independent cycle verification

The field workflow can execute:

```text
verified physical origin
→ bounded planner action
→ durable WindowPilot request
→ command ACK
→ measured actuator feedback
→ fresh post-action sensors
→ next physical origin
→ independent persisted-cycle verification
```

A final `PASS` cycle receipt is emitted only after the verifier reconstructs
the transition from persisted source artifacts.

If physical motion occurred but later verification fails, the top-level record
keeps:

```text
motion_performed = true
cycle_verified = false
status = BLOCKED_...
```

This prevents process failure from being misinterpreted as "no physical action
occurred."

## Suggested GEISA conformance cases

A useful first contribution would not need to standardize every field-tool
detail. A compact initial matrix could be:

| Case | Setup | Expected result |
| --- | --- | --- |
| Observe-only readiness | Connect tool and inspect target | No mutation |
| Target identity drift | Change target between readiness and execute | BLOCKED |
| Duplicate request | Replay same request and same payload | No duplicate mutation |
| Conflicting duplicate | Same request ID, different payload | BLOCKED |
| Ack without state change | Command accepted, measured target unchanged | FAIL |
| Stale post-action evidence | Reuse pre-command observation | BLOCKED |
| Uncertain transport outcome | Drop response after mutation boundary | UNCERTAIN / no automatic replay |
| Recovery | Restart after uncertain outcome | Re-observe before next mutation |
| Evidence reconstruction | Re-run verifier on persisted artifacts | PASS only when transition is internally consistent |

## What should remain out of scope

This note intentionally does not claim:

- distributed exactly-once execution across independent gateways without shared
  durable coordination;
- cryptographic hardware-rooted attestation;
- that one transport (HTTP, MQTT, CoAP, etc.) is required;
- that one serialization format is required for conformance evidence;
- that AirTrajectory/WindowPilot is a GEISA reference implementation.

Those are separate design choices.

## Potential next contribution

If the GEISA community finds this direction useful, the smallest useful next
step would be:

1. agree on the field-tool state/phase vocabulary;
2. define one machine-readable execution record;
3. map one existing GEISA conformance test to that record;
4. add one negative test for uncertain/replayed execution;
5. only then consider normative SHALL/SHOULD language in the specification.

That sequence keeps the proposal grounded in testable behavior instead of
prematurely standardizing a specific implementation.
