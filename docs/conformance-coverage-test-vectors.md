# Conformance Coverage Test Vectors v0.1

This artifact compresses the current AirTrajectory conformance-evidence work into
a small set of portable adversarial cases.

The goal is not to define a new conformance standard. It is to preserve
verification invariants that can be replayed against other systems.

## Why test vectors instead of another schema

A schema can prove that an artifact is well formed. It does not prove that the
artifact covers every obligation that should have been represented.

These vectors isolate four reusable questions:

1. Can a required execution disappear while the remaining evidence stays valid?
2. Can extra execution evidence appear outside the committed obligation?
3. Can a required conformance requirement disappear from a positive-only claim?
4. Does an explicit negative requirement outcome still count as covered?

The machine-readable vectors live at:

`test-vectors/conformance-coverage-v0.1.json`

and are executed by:

`tests/test_conformance_coverage_vectors.py`

## External collision points

These cases were distilled while comparing AirTrajectory's execution/evidence
model with two independently developed external directions:

- Margo's Conformance Test Toolkit architecture, CR-IDs, Spec Traceability
  Matrix, signed Conformance Result, and Public Conformance Registry;
- Veklom's independently developed EEE-Core execution-evidence format and
  verifier work.

No upstream adoption or authorship relationship is implied. The value of the
comparison is that independent systems converge on the same integrity problem:
cryptographic validity and positive traceability do not by themselves establish
coverage completeness.

## Durable invariants

```text
valid included evidence != complete evidence coverage

NOT_SATISFIED != MISSING

positive traceability != requirement-claim completeness
```

A future verifier can use different schemas, signatures, registries, and
outcome vocabularies while still applying these vectors.
