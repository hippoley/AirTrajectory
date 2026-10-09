# Multi-environment decision contract v0.2

This is the *product decision semantics* contract, not a physical simulator or
a safe-to-execute window-control authorization.

## Reproduce

```bash
python -m pip install -e .
python -m unittest tests.test_multi_environment_objective -v
python examples/compare_multi_environment_futures.py \
  examples/multi_environment_conflict_v0.2.json \
  --out artifacts/conflict-report.json
```

The fixture's `engineering_truth=false` is deliberate. CO₂, PM2.5,
temperature and humidity futures are hand-authored to test semantics.
The outdoor PM2.5 reading is an illustrative boundary condition, not a
physical transport simulation.

## Consumer input

`compare_candidate_futures(candidates, objective, origin_openings)` requires:

- at least two uniquely named candidates, including `HOLD`;
- an explicit `origin` with `opening_pct`, `opening_kind`, `rain`, and
  initial zone metrics for every declared objective;
- `time_grid_min`, starting at 0 and strictly increasing, **identical**
  for every candidate;
- `series_by_metric` with one finite series per zone and field; the
  first value **must match the origin**;
- `actions` with typed origin opening IDs and target percentages in
  [0, 100]; absent actions imply unchanged openings;
- `duration_min` (active intervention duration, 0 for HOLD) within the
  common horizon;
- `rain` matching the common origin and `provenance.kind` plus a
  consistent `provenance.backend`.

All candidates must share identical canonical-origin SHA-256, time grid,
zone coverage and declared backend evidence class. The SHA-256 detects
mismatched input objects; it **does not attest** that the sensor, model or
simulator produced authentic results.

## Ranking

1. Check all declared hard limits on the supplied future samples.
2. Reject any candidate with a hard violation.
3. Among feasible candidates, minimize ordered soft priorities
   lexicographically; never silently skip a missing metric.
4. If none are feasible, return `NO_FEASIBLE_CANDIDATE`.
5. Always return `execution_authorized=false`.

Rain blocks *increasing* an exterior window opening, not closing it or
changing an interior door. The caller must still enforce real hardware,
weather, sensor freshness, manual override and physical authorization.

## Strict boundary

This v0.2 surface is suitable for third-party **contract testing** and
counterfactual comparison. It is not sufficient for deployment until
physics-backed candidate trajectories with provenance and independently
audited physical feedback are supplied.

Next engineering gates: #201 US3/US4/US6/US7 and US8 field reality; unify
#202's backend observation projection under this one ObjectiveContract
rather than shipping competing ranking APIs.
