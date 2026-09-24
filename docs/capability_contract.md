# Capability contract

Every public claim should map to an executable check.

| Claim | Check |
|---|---|
| topology validates unknown nodes | `test_invalid_topology_rejected` |
| opening an outdoor path lowers CO2 in the baseline model | `test_opening_reduces_co2` |
| rollout preserves proposed/executed actions | `test_rollout_preserves_learning_fields` |
| end-to-end rollout writes a trajectory | `examples/single_room_rollout.py` |
| trajectory preserves semantic action, sensor provenance, and actuator feedback | `test_physical_trajectory_schema_preserves_semantic_and_feedback_layers` |
| measured actuator position is never silently replaced by an estimate | `test_feedback_separates_measured_and_estimated_position` |

| synthetic physical driver can exercise sensor → rule → safety → command → feedback → JSONL | `test_fake_physical_runtime_records_tau0_contract` |
| rain safety can preserve proposed action while executing safe close | `test_rain_safety_intervention_overrides_rule_policy` |

| stale sensor evidence blocks physical control | `test_stale_sensor_blocks_physical_control` |
| deployments requiring measured position reject estimate-only feedback | `test_measured_feedback_gate_rejects_estimate_only_driver` |

**Real τ₀ status: NOT CAPTURED.** A real τ₀ requires a non-fake driver, fresh sensor evidence, an actual actuator command, feedback provenance, and persisted trajectory output.

> `FakePhysicalWindowDriver` is contract-test evidence only. It is not a real actuator integration and must never be presented as physical τ₀ evidence.

Upcoming claims must not be added to the README until they have a corresponding test or evaluation.
