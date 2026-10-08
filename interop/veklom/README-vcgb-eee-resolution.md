# Veklom VCGB / EEE coverage-layer resolution

Issue `reprewindai-dev/veklom-FRONTEND#146` began with a narrow omission
counterexample:

```text
expected: A, B
evidence: A only
```

The question was whether EEE itself needed an independently committed expected
execution set in order to detect the missing B.

Reviewing VCGB resolves the boundary without extending EEE.

## Existing layering

VCGB supplies the expected test population and run-completeness rules:

- the canonical scenario set is bound by `suite_hash`;
- the harness owns the scenario population;
- the harness calls `submit_intent`;
- `fetch_evidence` must return EEE evidence for every submitted intent,
  including denials;
- headline claims require full result bundles;
- failed scenarios may not be omitted;
- missing scenario IDs invalidate a bundle on its face.

EEE can therefore remain focused on:

- integrity and verification of each execution envelope;
- terminal evidence for allowed and denied attempts;
- evidence-chain semantics.

The resolved split is:

```text
VCGB
  expected population / suite completeness
        ↓
EEE
  per-execution evidence integrity
```

This is a better result than adding another schema object because it reduces
overlap while preserving the original coverage invariant.

The issue was closed by its author after this boundary was identified. That
closure is not maintainer endorsement; it is a documented cross-project scope
resolution based on Veklom's published VCGB/EEE design.
