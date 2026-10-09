# Minimal decision SDK v0.1 (read-only)

For an external integrator, the stable import path is:

```python
import json
from pathlib import Path
from airtrajectory import evaluate

fixture = json.loads(
    Path("examples/multi_environment_conflict_v0.2.json").read_text()
)
report = evaluate(
    candidates=fixture["candidates"],
    origin_openings=fixture["origin_opening_pct"],
    user_goal=fixture["user_goal"],
)
assert report["execution_authorized"] is False
print(report["recommended"])
```

`user_goal` currently accepts **only** the exact deterministic presets in
`airtrajectory.objective`. Alternatively supply an explicit
`ObjectiveContract` with the `objective=` keyword. Supplying both or
neither fails closed.

**This API compares supplied futures. It does not generate physics, infer
missing PM2.5/thermal results, authenticate simulator provenance, prove
post-training advantage, or execute any hardware.** The bundled multi-
environment fixture is hand-authored and declares `engineering_truth=false`.

For an immutable software origin, `CanonicalWorldState` and `EvidenceRef`
are also importable from `airtrajectory`; they do not confer E4 measured
physical status or field actuation authorization.

Next P0-8 closure requires a non-owner project retaining this API and a
pinned compatibility test. Internal unit tests alone are insufficient.
