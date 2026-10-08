# Emilia CAP-1 coverage-layer resolution

Issue `emiliaprotocol/emilia-protocol#914` originally asked whether
AirTrajectory's coverage vectors could map into Emilia's existing verifier
semantics.

Reviewing the native Emilia corpus resolves the core question without adding a
new primitive.

## Existing coverage composition

Emilia already separates two layers:

1. **examined-set coverage**
   - CAP-1 coverage statement;
   - explicit eligible/examined-set commitments;
   - one result binding per examined unit;
   - eligible/examined roots and counts;
   - signed coverage-reconciliation attestation.

2. **source-population completeness**
   - not inferred from examined-set coverage;
   - remains an explicit nonclaim unless separately proven.

The key boundary is therefore:

```text
closed examined-set coverage
!=
proof that the source population itself was complete
```

That aligns directly with AirTrajectory's portable completeness distinction
without requiring Emilia to adopt an AirTrajectory schema.

## Result

The interoperability crosswalk can be marked resolved by existing layering:

```text
AirTrajectory expected-set coverage
        ↓
CAP-1 + examined-set composition

AirTrajectory coverage != completeness
        ↓
CoverageDoesNotProveCompleteness
+ source_population_completeness nonclaim
```

This is a scope resolution based on Emilia's published code/docs, not a claim
of maintainer adoption or endorsement.
