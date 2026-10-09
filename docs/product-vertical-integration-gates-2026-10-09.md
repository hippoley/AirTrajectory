# Product vertical-integration gate — 2026-10-09

## Development policy switch
Stop treating isolated defensive checks as the unit of product progress. The default accepted increment is a **complete vertical user path** with a genuine upstream source, policy/physics consumer, independent verifier, relevant cross-story tests, and exact evidence boundary. Safety fixes remain permissible when they block this path or address an actual P0.

## Current first slice
Imported or corrected layout -> geometry/readiness -> real transient ContamX compiled PRJ -> same-origin HOLD/INDEPENDENT/JOINT -> physics trajectories -> portable policy benchmark -> independent semantic recomputation -> artifact with solver/version/provenance. This slice targets US1/2/5/6/11/12; failures reopen the relevant story.

Current runner: `examples/run_contam_joint_golden_case.py --policy-benchmark`. It already executes real ContamX, but currently uses the fixed example unless the caller supplies a compatible layout/PRJ/provenance/case. Merely supplying an arbitrary unseen geometry does not prove readiness or physics compilation.

## Implemented in this increment
1. Repair genuine integration regression: old toy bridge test expected checksum failure, but score replay now catches frame tampering first (`594b9a1b`).
2. Add `verify_policy_benchmark_report` to recompute score/metrics/Pareto from **raw solver branches, separate case and topology**, comparing with stored benchmark receipt (`eb1ebf66`). This proves consistency, not solver identity or field authenticity.
3. Wire independent recomputation as a required step in the **real ContamX product runner** when `--policy-benchmark` is used (`a882fb29`).
4. Cross-module regression: retained receipt verifies; modified score is rejected (`b0f2ae84`).

## Closure gates
| Layer | Current state | Must pass |
| --- | --- | --- |
| Code and product runner | Committed, CI pending | latest HEAD core + contam-real jobs both green |
| Imported geometry | PARTIAL | unseen user layout -> corrected topology -> PRJ compiler, no source code edits, provenance, readiness |
| Real solver | PARTIAL E3 | run matched HOLD/Independent/Joint and export raw branches, engine version and model digest |
| Benchmark integrity | PARTIAL | independent verifier recomputes from raw branches; negative tamper/injected-failure tests |
| Five-policy learning comparison | BLOCKED | real solver heldout families, shared budget/horizon and learned policies |
| Physical actuation | BLOCKED E4 | commissioned WindowPilot, fresh measured start and result, reconciliation and replan |
| Independent adoption | UNVERIFIED E5 | non-owner retained test or repeatable independent consumer |

## Ten audit dimensions
Functional PARTIAL; State PARTIAL; Integration PARTIAL; Safety/Correctness PARTIAL; Performance NOT VERIFIED; Maintainability PARTIAL; Observability/Traceability PARTIAL; Testability CI PENDING; User Value BLOCKED end-to-end; External Compatibility PARTIAL. No complete story is Verified Closed.

## Reuse and scope
Continue using NIST CONTAM/ContamX and the existing portable policy-benchmark contract. Evaluate BOPTEST/BACnet/IFC interface compatibility separately against version, licensing, interface fit and actual execution; do not add packages solely for naming a standard. Never convert toy E2, solver E3, physical E4, independent use E5 into one claim.
