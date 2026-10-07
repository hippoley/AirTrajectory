"""Behavior probe for contamxpy setZoneAddMass.

This does not promote state continuation. It only determines whether the binding
mutates zone contaminant state immediately, after a simulation step, or behaves
like another kind of source/input.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prj", type=Path)
    parser.add_argument("--zone", type=int, default=1)
    parser.add_argument("--contaminant", type=int, default=0)
    parser.add_argument("--mass", type=float, default=1e-6)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    from contamxpy import cxLib

    engine = cxLib(str(args.prj), 0, True, None)
    started = False
    try:
        status = engine.setupSimulation(1)
        if status not in (None, 0):
            raise RuntimeError(f"setupSimulation failed: {status}")
        started = True
        if not hasattr(engine, "setZoneAddMass"):
            raise RuntimeError("contamxpy does not expose setZoneAddMass")

        before = float(
            engine.getZoneMassFraction(args.zone, args.contaminant)
        )
        set_status = engine.setZoneAddMass(
            args.zone,
            args.contaminant,
            float(args.mass),
        )
        immediate = float(
            engine.getZoneMassFraction(args.zone, args.contaminant)
        )
        engine.doSimStep(1)
        after_step = float(
            engine.getZoneMassFraction(args.zone, args.contaminant)
        )

        payload = {
            "marker": "CONTAM_ZONE_ADD_MASS_BEHAVIOR_PROBED",
            "contam_version": (
                engine.getVersion()
                if hasattr(engine, "getVersion")
                else "unknown"
            ),
            "zone": args.zone,
            "contaminant": args.contaminant,
            "requested_mass": float(args.mass),
            "set_status": set_status,
            "before_mass_fraction": before,
            "immediate_mass_fraction": immediate,
            "after_step_mass_fraction": after_step,
            "immediate_delta": immediate - before,
            "after_step_delta_from_before": after_step - before,
            "semantics_verified": False,
            "state_reinjection_verified": False,
        }
        rendered = json.dumps(payload, indent=2, sort_keys=True)
        print(rendered)
        if args.out is not None:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(rendered + "\n", encoding="utf-8")
        return 0
    finally:
        if started:
            engine.endSimulation()


if __name__ == "__main__":
    raise SystemExit(main())
