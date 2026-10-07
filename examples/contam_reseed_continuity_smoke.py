"""Real ContamX PRJ re-seed continuity experiment.

Compare a continuous two-step transient run against:
1 step on the source PRJ
→ write solved zone mass fractions into Section 15 of a sibling PRJ
→ 1 step on the re-seeded PRJ

This is a state-equivalence experiment under identical static boundaries and
controls. It does not claim full restart/time continuity.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.contam import ContamXSession, co2_mass_fraction_to_ppm
from airtrajectory.contam_continuation import compare_continuation_observations
from airtrajectory.contam_prj_reseed import reseed_initial_zone_mass_fractions


def capture(session: ContamXSession, zones, paths):
    return {
        "co2_ppm": {
            str(zone): co2_mass_fraction_to_ppm(
                session.zone_mass_fraction(zone, 0)
            )
            for zone in zones
        },
        "mass_fraction": {
            str(zone): session.zone_mass_fraction(zone, 0)
            for zone in zones
        },
        "path_flow_kg_s": {
            str(path): session.path_flow(path)
            for path in paths
        },
        "opening_pct": {},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prj", type=Path)
    parser.add_argument("--zones", type=int, default=3)
    parser.add_argument("--paths", type=int, default=5)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--reseeded-prj", type=Path)
    args = parser.parse_args()

    zones = list(range(1, args.zones + 1))
    paths = list(range(1, args.paths + 1))

    with ContamXSession(args.prj) as continuous:
        continuous.step()
        step1 = capture(continuous, zones, paths)
        continuous.step()
        step2 = capture(continuous, zones, paths)

    source_text = args.prj.read_text(encoding="utf-8")
    reseeded = reseed_initial_zone_mass_fractions(
        source_text,
        {zone: step1["mass_fraction"][str(zone)] for zone in zones},
    )
    reseeded_path = args.reseeded_prj or args.prj.with_name(
        args.prj.stem + ".reseeded.prj"
    )
    reseeded_path.write_text(reseeded["text"], encoding="utf-8", newline="\n")

    with ContamXSession(reseeded_path) as resumed:
        resumed.step()
        resumed_step = capture(resumed, zones, paths)

    comparison = compare_continuation_observations(
        continuous=step2,
        resumed=resumed_step,
        co2_tolerance_ppm=1.0,
        flow_tolerance_kg_s=1e-6,
        opening_tolerance_pct=1e-9,
    )
    payload = {
        "marker": "REAL_CONTAM_PRJ_RESEED_CONTINUITY_EXECUTED",
        "source_prj": str(args.prj),
        "reseeded_prj": str(reseeded_path),
        "step1": step1,
        "continuous_step2": step2,
        "resumed_step1": resumed_step,
        "reseed_receipt": reseeded["receipt"],
        "comparison": comparison,
        "evidence_boundary": (
            "state-equivalence under identical static boundaries and controls; "
            "simulation clock/restart-file continuity not established"
        ),
        "full_restart_verified": False,
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    print(rendered)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
