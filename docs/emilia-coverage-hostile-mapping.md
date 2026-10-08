# Emilia hostile-vector mapping (review artifact)

This is a deliberately small bridge from AirTrajectory's portable coverage
vectors into the vocabulary already used by Emilia Protocol's conformance and
formal verification work.

It does **not** introduce a new schema, protocol, verifier, or claim format.

The mapping exists only to make issue
`emiliaprotocol/emilia-protocol#914` concrete enough to review.

## Why this mapping is narrow

Emilia already has:

- the formal/security invariant `CoverageDoesNotProveCompleteness`;
- hostile-vector categories;
- omission/substitution checks;
- explicit unavailable / indeterminate / refusal semantics;
- conformance suites with fixed vector IDs and expected verdicts.

AirTrajectory contributes only three portable distinctions that can be tested
against that existing machinery:

```text
valid included evidence != complete coverage

positive-only claim set != complete requirement coverage

explicit negative outcome != missing outcome
```

The machine-readable review mapping is:

`interop/emilia/coverage-hostile-mapping-v0.1.json`

## Proposed review question

For each mapped row, can an Emilia-native hostile vector express the same
boundary using existing verdicts and runner fields?

If yes, the useful contribution is a vector mapping or regression case, not a
new protocol surface.

If no, the mismatch identifies the exact semantic gap to discuss.

## Attribution boundary

This repository does not claim that Emilia adopted these vectors. Adoption
would require an Emilia maintainer to accept, adapt, cite, or request the
mapping.
