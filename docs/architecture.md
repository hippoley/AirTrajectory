# Architecture

AirTrajectory is a learning and simulation core, not a device runtime.

## Ownership boundaries

### AirTrajectory owns

- room / door / window topology
- physics backend abstraction
- trajectory generation
- reward vectors
- counterfactual branches
- offline learning datasets
- transfer benchmarks

### Device runtimes own

- actuator commands
- sensor transport
- hardware safety
- local manual override
- device protocols

## Key invariant

A trajectory must preserve:

- observation
- proposed action
- executed action
- intervention reason
- next observation
- raw reward vector
- provenance

Never rewrite a safety override as though the policy proposed it.

## Transfer target

The primary research target is unseen-topology transfer.

Training and evaluation must split by topology, not just by time or random transitions.
