# Emilia native crosswalk for coverage completeness

This review artifact narrows the discussion in
`emiliaprotocol/emilia-protocol#914` by checking AirTrajectory's portable
coverage vectors against Emilia's existing native semantics.

## Result

Two of the three original distinctions already have clear native homes:

- **explicit negative outcome != missing outcome** is already represented by
  Emilia's signed-denial / four-outcome semantics. A decline or denial remains
  explicit, verifiable evidence even though it cannot authorize.
- **required material omission** is already represented by hostile omission
  fixtures such as `required-object-omission`.

The remaining cross-project question is therefore narrower:

> What authoritative Emilia object establishes the expected execution or source
> population before a verifier evaluates a completeness claim?

Emilia already has the formal invariant
`CoverageDoesNotProveCompleteness`, and its bounded-execution draft states that
outside-plan claims require an external inventory root with a
population-completeness boundary.

So the useful interoperability question is not whether Emilia understands
omission. It does.

The remaining question is **where the expected population is committed and how
that commitment is bound to the evidence claim**.

Machine-readable crosswalk:

`interop/emilia/native-coverage-crosswalk-v0.1.json`

This file is review-only and does not claim Emilia adoption.
