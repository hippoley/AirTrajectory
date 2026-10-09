# Same-origin toy ablation v0.1 — reproducible learning plumbing

This is a deliberately limited **product/research gate**, not an engineering
airflow benchmark or evidence that reinforcement learning improves control.

## Run locally

```bash
python -m unittest tests.test_toy_ablation -v
python examples/export_toy_ablation.py --train-count 12 --test-count 3 --horizon 20
python -m http.server 8000 -d web
# Open http://localhost:8000/ablation.html
```

GitHub Pages builds the artifact using the **same Python exporter** and checks
it with `verify_toy_ablation` before publishing. The browser reads the
generated JSON; it does **not** implement an independent toy physics engine.

## What is genuinely compared

- HOLD (no actuator commands)
- Independent (at most one exterior window active each step)
- Rule Joint (existing `MultiWindowRuleAgent`)
- BC (existing `TopologyBCPolicy`)
- Offline-Q (existing `TopologyOfflineQPolicy`)

All five policies start from an identical SHA-256-hashed origin, identical
5-room chain topology, horizon, 1-minute toy time step and backend. Each
episode exports all backend CO2 and opening states, proposed/executed actions,
safety interventions, plus environmental and movement metrics. The artifact
has a deterministic content checksum; this is **not a signature** and does
not establish trust in the producer.

Training uses existing 2–4-room chain rule demonstrations; test uses 5-room
chain with disjoint seeds. This is a size/ID-transfer experiment, **not**
held-out structural-family generalization.

## Truth boundaries

- Toy CO2 mixing is **not** CONTAM, CFD or real airflow.
- No PM2.5, temperature or humidity trajectory is invented.
- The Independent baseline is a documented heuristic, **not** an untrained LLM.
- BC and Offline-Q still act on per-window local features; they are not yet
  a genuinely jointly trained multi-window policy.
- Aggregate numbers are descriptive, not statistical evidence of improvement.
- The schematic room view is a graph representation, not an architectural plan.
- No physical tau0 or measured window actuation is claimed.
- The browser cannot edit a topology and rerun physics; it replays immutable
  backend experiments and compares policies.
- The artifact is validated against the declared toy schema; it is not a
  portable CONTAM/physical trajectory interchange standard.

## Next experiment (required for the actual thesis)

Replace the toy runner with one physics-grounded same-origin experiment over
CONTAM-derived joint action trajectories, add an otherwise comparable
non-post-trained agent baseline, and hold out **hub / loop / irregular**
structural families. Compare identical action support, objective, horizon,
safety rules, and compute multi-seed uncertainty. Never mark the
post-training hypothesis proven without those controls.

Tracked by #201, #205 and #206.
