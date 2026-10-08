# Structured Topology Intake v0.1

AirTrajectory now treats a corrected structured topology as a first-class input
source.

This deliberately separates **recognition** from **control semantics**:

```text
CAD / SVG / image / 3D / Brick / Haystack / custom parser
                    ↓
        external recognition/correction
                    ↓
          structured-topology contract
                    ↓
        AirTrajectory shared runtime
                    ↓
UI / trajectory / VentilationPath / physics adapters / policy
```

The parser does not need to live inside AirTrajectory.

## Why this matters

A new floorplan recognizer, BIM extractor, computer-vision model, or future
foundation model can be replaced without changing the downstream control
contract.  The stable asset is the topology boundary.

## Current acceptance

`source_kind=structured-topology` is accepted when:

- room/wall/opening connectivity is valid;
- `arbitrary_topology_import=true`;
- opening placement/state semantics satisfy the existing contract.

The same cross-topology acceptance suite then verifies that the imported
topology reaches UI/physics/spatial/trajectory/policy consumers without fixed
W1/W2/W3 assumptions.

## Non-claim

AirTrajectory does not yet claim automatic CAD/SVG/raster recognition.  v0.1
claims that an external importer can hand off a corrected new topology without
requiring downstream source changes.
