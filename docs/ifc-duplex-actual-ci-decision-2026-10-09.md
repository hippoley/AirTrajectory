# External IFC evidence decision — run 37900227524

## Actual upstream receipt
- CI: https://github.com/hippoley/AirTrajectory/actions/runs/37900227524 — SUCCESS for **importer diagnostic execution**, **not** end-to-end physics.
- Artifact: `duplex-ifc-control-readiness`, ID `11601901565`, ZIP digest `sha256:ae1dcc6f79bc03cdedf569555b274f0c841a76f015360cbead80e1e7dcc3a407`.
- Source: `https://raw.githubusercontent.com/andyward/XBimDemo/master/Xbim.TestApp/Duplex_A_20110907.ifc`
- Source SHA-256: `b347a2c8aa8fff6db896a4417a9c50c22ac0ccd7c5cfc22b99b8d29336c606ed`
- Source size: 2,380,763 bytes, IFC2X3.
- 21 spaces, 14 doors, 24 windows; boundary mappings 13/14 doors and 14/24 windows.
- Overall readiness: `BLOCKED`. **11 AMBIGUOUS_SPACE_ADJACENCY** records. 10 have no mapped space; one opening has three spaces: `1aj$VJZFn2TxepZUBcKpac` (candidates `0BTBFw6f90Nfh9rP1dlXre`, `0BTBFw6f90Nfh9rP1dlXri`, `2gRXFgjRn2HPE$YoDLX3FV`).

## Exact unresolved opening IDs
```text
1aj$VJZFn2TxepZUBcKpac (3 candidates; human review)
1hOSvn6df7F8_7GcBWlSp1
1hOSvn6df7F8_7GcBWlSnC
1hOSvn6df7F8_7GcBWlS1M
1hOSvn6df7F8_7GcBWlS4Q
1l0GAJtRTFv8$zmKJOH4u1
1l0GAJtRTFv8$zmKJOH4oq
1l0GAJtRTFv8$zmKJOH4kJ
1l0GAJtRTFv8$zmKJOH4gQ
1Eo2$BaHX42AEkDvQQDocD
1Eo2$BaHX42AEkDvQQDoy2
```

## Gate decision
**DO NOT compile a physically trusted PRJ from the uncorrected 38-opening ALL_OPENINGS model.** Import validity does not prove opening-to-space connectivity. No fabricated adjacency, geometry or physics metrics may be inserted merely to obtain PASS.

Next vertically integrated action: derive a **reviewable controlled-opening subset** from the real report, rerun `inspect_ifc_control_readiness.py --control-opening <IFC GlobalId>` for the exact subset and verify surrounding space geometry, volume, exterior/boundary meaning and proper physical controls. Preserve all excluded IDs in a scope receipt. An ALL_OPENINGS verdict must remain BLOCKED even if a supported subset is READY. Then compile/execute real transient ContamX against that *same upstream source SHA*, capture PRJ digest and raw branches, feed offline benchmark replay. If geometry still not adequate, keep physics BLOCKED.

## Evidence ladder
- E3 IFC source and diagnostic receipt: VERIFIED ONLY FOR RUNNING THE EXTERNAL INPUT.
- E3 same-source ContamX physics trajectory: NOT VERIFIED.
- E4 measured device action: NOT VERIFIED.
- E5 non-owner retained reuse: NOT VERIFIED.
- US1/2/5/6/11/12: OPEN. No Verified Closed claim.
