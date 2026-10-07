"""A/B behavior probe for contamxpy setZoneAddMass.

Runs deterministic sibling sessions from the same PRJ:
- baseline: no mass adjustment
- 1x: setZoneAddMass(mass)
- 2x: setZoneAddMass(2 * mass)

This does not claim state continuation. It measures immediate and one-step effects
and checks whether the response is directionally and approximately linear.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def run_case(prj: Path, zone: int, contaminant: int, mass: float):
    from contamxpy import cxLib

    engine = cxLib(str(prj), 0, True, None)
    started = False
    try:
        status = engine.setupSimulation(1)
        if status not in (None, 0):
            raise RuntimeError(f"setupSimulation failed: {status}")
        started = True
        if not hasattr(engine, "setZoneAddMass"):
            raise RuntimeError("contamxpy does not expose setZoneAddMass")

        before = float(engine.getZoneMassFraction(zone, contaminant))
        set_status = None
        if mass != 0.0:
            set_status = engine.setZoneAddMass(
                zone,
                contaminant,
                float(mass),
            )
        immediate = float(engine.getZoneMassFraction(zone, contaminant))
        engine.doSimStep(1)
        after_step = float(engine.getZoneMassFraction(zone, contaminant))
        return {
            "mass": float(mass),
            "set_status": set_status,
            "before_mass_fraction": before,
            "immediate_mass_fraction": immediate,
            "after_step_mass_fraction": after_step,
        }
    finally:
        if started:
            engine.endSimulation()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prj", type=Path)
    parser.add_argument("--zone", type=int, default=1)
    parser.add_argument("--contaminant", type=int, default=0)
    parser.add_argument("--mass", type=float, default=1e-6)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    baseline = run_case(args.prj, args.zone, args.contaminant, 0.0)
    one_x = run_case(
        args.prj,
        args.zone,
        args.contaminant,
        float(args.mass),
    )
    two_x = run_case(
        args.prj,
        args.zone,
        args.contaminant,
        float(args.mass) * 2.0,
    )

    immediate_effect_1x = (
        one_x["immediate_mass_fraction"]
        - baseline["immediate_mass_fraction"]
    )
    immediate_effect_2x = (
        two_x["immediate_mass_fraction"]
        - baseline["immediate_mass_fraction"]
    )
    after_step_effect_1x = (
        one_x["after_step_mass_fraction"]
        - baseline["after_step_mass_fraction"]
    )
    after_step_effect_2x = (
        two_x["after_step_mass_fraction"]
        - baseline["after_step_mass_fraction"]
    )

    def ratio(double, single):
        if abs(single) < 1e-20:
            return None
        return double / single

    payload = {
        "marker": "CONTAM_ZONE_ADD_MASS_AB_PROBED",
        "zone": args.zone,
        "contaminant": args.contaminant,
        "base_mass": float(args.mass),
        "baseline": baseline,
        "one_x": one_x,
        "two_x": two_x,
        "effects": {
            "immediate_1x": immediate_effect_1x,
            "immediate_2x": immediate_effect_2x,
            "after_step_1x": after_step_effect_1x,
            "after_step_2x": after_step_effect_2x,
            "immediate_2x_over_1x": ratio(
                immediate_effect_2x,
                immediate_effect_1x,
            ),
            "after_step_2x_over_1x": ratio(
                after_step_effect_2x,
                after_step_effect_1x,
            ),
        },
        "semantics_verified": False,
        "state_reinjection_verified": False,
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    print(rendered)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
