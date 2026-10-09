# IFC Engineering Package v0.1 — executable compiler handoff

This is the first source-bound engineering package adapter from an imported IFC layout into the **existing** CONTAM engineering build. It is not an approved engineering data set for the Duplex sample and does not grant solver-run authorization merely from a form checkbox.

## Package contract
The JSON object must include `schema_version=airtrajectory-ifc-engineering-package-v0.1`, `source_ifc_sha256`, `topology_id`, `layout_sha256`, `scope_receipt_sha256`, `opening_treatments` keyed by **every source IFC opening ID**, `approval` with reviewer/role/source binding, plus `metric_evidence`, `airflow_evidence`, `boundary_evidence`, `prj_profile`, and `prj_review_evidence`. Every one of those five inputs must carry the same `source_ifc_sha256`. Values must be supplied from actual independent engineering measurements and reviews, not generated defaults.

## How to run (only after approved engineering information is available)
```bash
python -m examples.compile_ifc_engineering_package \
  --package reviewed-engineering-package.json \
  --layout corrected-imported-layout.json \
  --ifc-readiness duplex-control-readiness.json \
  --candidate-scope duplex-candidate-scope.json \
  --out duplex-engineering.prj \
  --receipt duplex-build-receipt.json
```

The adapter rejects source mismatch, non-imported layouts, missing opening treatments, blocked openings incorrectly designated controllable, lack of review and missing input bundles **before invoking** `build_engineering_contam_project`. The existing four typed evidence compilers, engineering readiness check, PRJ serializer and physical constraints remain in effect.

## Current blockers
The public Duplex source remains IFC-ready-for-diagnostics but **physics BLOCKED** until the 11 ambiguous openings receive engineering-reviewed treatment, and all 27 initial candidates receive reviewed boundary and airflow parameters, weather, contaminant baseline, geometry profile and serialization review. The workflow evidence of missing approvals is not interchangeable with approval. No real Duplex PRJ/ContamX run/strategy score has been produced in this increment.

## Validation and scope
`tests/test_ifc_engineering_package.py` uses adversarial source-drift/nonapproval/incomplete-scope checks and a compiler-interface spy to confirm the existing build is *actually invoked* only after package preconditions. This is a mocked integration boundary; a real supported IFC engineering package and actual ContamX execution are still necessary for E3. Store PRJ digest, solver version, raw branches and offline score verification at that stage.
