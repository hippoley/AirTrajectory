# Capability contract

Every public claim should map to an executable check.

| Claim | Check |
|---|---|
| topology validates unknown nodes | `test_invalid_topology_rejected` |
| opening an outdoor path lowers CO2 in the baseline model | `test_opening_reduces_co2` |
| rollout preserves proposed/executed actions | `test_rollout_preserves_learning_fields` |
| end-to-end rollout writes a trajectory | `examples/single_room_rollout.py` |

Upcoming claims must not be added to the README until they have a corresponding test or evaluation.
