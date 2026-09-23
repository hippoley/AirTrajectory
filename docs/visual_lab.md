# AirTrajectory Physical Learning Lab

The web lab is not a dashboard. It is the visual surface of the trajectory-learning system.

## Visual semantics

Particles are a semantic representation of the current flow field:

- direction → airflow direction
- animation speed → local velocity, with compressed visual dynamic range
- particle density → relative flow/flux
- sparse or nearly static regions → dead-zone signal

The first implementation is deliberately qualitative and runs fully in the browser. It must not be described as CFD or engineering-grade airflow prediction.

## Interaction model

The lab is organized around three linked objects:

1. **House** — topology and current physical state
2. **Time** — the actual trajectory
3. **Possible futures** — counterfactual branches from any selected state

This is intentionally different from a settings-heavy simulator UI.

## Fidelity ladder

The same action/observation vocabulary should eventually drive:

- Fast browser physics
- CONTAM
- CFD replay/calibration
- Real-room observations

The visualization must expose which backend produced a result.

## Colab visual reference

The supplied Colab URL currently requires authentication when fetched outside the user's browser, so its notebook code/frames have not been copied. Particle semantics from the prior project direction are implemented first; exact motion/styling can be aligned after the notebook contents are accessible.
