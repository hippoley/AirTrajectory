# Policy Benchmark Contract v0.1

AirTrajectory's durable claim is not that one controller is universally best.

The v0.1 benchmark defines a portable comparison surface so rule-based,
optimization, RL, future foundation-model, and third-party controllers can be
evaluated under the same physical origin and horizon.

## Required baselines

Every comparable receipt includes:

- `HOLD`
- `INDEPENDENT`
- at least one `JOINT:...` candidate

A learned policy may be added, but it never removes the baselines.

## Required evidence

The benchmark reports multiple outcomes instead of using scalar reward as the
proof surface:

- mean CO2 AUC;
- worst-zone CO2 AUC;
- peak CO2;
- worst-zone peak;
- zone-seconds above threshold;
- time-to-safe when achieved;
- actuator movement;
- explicit availability for safety violations;
- explicit availability for prediction error.

The scalar return may be retained for backward compatibility, but the benchmark
does not select a winner from it.

## Pareto semantics

The default report emits a Pareto frontier over metrics that are currently
available across all candidates. This keeps real trade-offs visible rather than
hiding them behind a single weight vector.

## Third-party adoption target

A third party should be able to emit a receipt conforming to:

`schemas/policy-benchmark-v0.1.schema.json`

without importing the AirTrajectory Python package.

That is the compatibility surface we want other simulators, controllers, and
building-control projects to preserve.

## Boundary

v0.1 is intentionally CO2 + actuator-movement focused because those are the
metrics with current end-to-end support. PM2.5, temperature, humidity, TVOC,
HCHO, safety-event, and physical prediction-error metrics are promoted only
when the corresponding state and physics evidence is real enough to support
them.

## BOPTEST alignment

The v0.1 IAQ discomfort metric intentionally follows the same physical meaning and numerical integration style used by BOPTEST core KPIs: prepend the declared origin to the rollout, integrate only the positive CO2 deviation above the declared threshold with trapezoidal integration over time, then average across zones. AirTrajectory receipts additionally publish the threshold map and integration semantics so the value can be independently recomputed. AirTrajectory retains additional trajectory-native metrics because natural-ventilation control also needs worst-zone, action-movement, prediction-error, and physical-reconciliation evidence.
