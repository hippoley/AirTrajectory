"""Runtime capability probe for truthful CONTAM state continuation.

The probe is intentionally conservative. It reports callable surface area from the
installed contamxpy engine and classifies whether AirTrajectory has a verified way
to continue from an arbitrary solved state.

Supported strategy order:
1. native runtime state setter / snapshot API
2. native CONTAM restart-file continuation
3. deterministic PRJ re-seed of solved contaminant concentrations

Only a separately verified continuity experiment may promote any strategy to
state_reinjection_verified=True.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import inspect
import json
from pathlib import Path
from typing import Any, Iterable


INTERESTING_TOKENS = (
    "restart",
    "state",
    "mass",
    "fraction",
    "concentration",
    "zone",
    "save",
    "load",
    "initial",
    "result",
)


def _sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def _safe_signature(value: Any) -> str | None:
    try:
        return str(inspect.signature(value))
    except (TypeError, ValueError):
        return None


def _public_callables(obj: Any) -> list[dict[str, Any]]:
    rows = []
    for name in sorted(dir(obj)):
        if name.startswith("_"):
            continue
        try:
            value = getattr(obj, name)
        except Exception:
            continue
        if not callable(value):
            continue
        rows.append(
            {
                "name": name,
                "signature": _safe_signature(value),
            }
        )
    return rows


def _matching_names(
    callables: Iterable[dict[str, Any]],
    tokens: tuple[str, ...] = INTERESTING_TOKENS,
) -> list[dict[str, Any]]:
    out = []
    for row in callables:
        lowered = row["name"].lower()
        if any(token in lowered for token in tokens):
            out.append(dict(row))
    return out


def _find_names(callables: Iterable[dict[str, Any]], *patterns: str) -> list[str]:
    names = []
    for row in callables:
        lowered = row["name"].lower()
        if all(pattern.lower() in lowered for pattern in patterns):
            names.append(row["name"])
    return sorted(names)


@dataclass(frozen=True)
class ContinuationStrategy:
    strategy_id: str
    available: bool
    verified: bool
    evidence: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "available": bool(self.available),
            "verified": bool(self.verified),
            "evidence": self.evidence,
        }


def classify_continuation_surface(engine: Any) -> dict[str, Any]:
    callables = _public_callables(engine)
    names = {row["name"] for row in callables}

    zone_mass_getters = sorted(
        name for name in names
        if name.lower() in {"getzonemassfraction", "getzonemf"}
    )
    zone_mass_setters = sorted(
        name for name in names
        if (
            ("set" in name.lower())
            and ("zone" in name.lower())
            and (
                "massfraction" in name.lower()
                or name.lower().endswith("mf")
                or "concentration" in name.lower()
            )
        )
    )
    zone_mass_adjusters = sorted(
        name for name in names
        if (
            "set" in name.lower()
            and "zone" in name.lower()
            and "addmass" in name.lower()
        )
    )
    restart_methods = sorted(
        name for name in names
        if "restart" in name.lower()
        or name.lower() in {"resget", "resout", "set_urst"}
    )
    state_methods = sorted(
        name for name in names
        if "state" in name.lower()
        and ("get" in name.lower() or "set" in name.lower())
    )

    native_runtime = ContinuationStrategy(
        strategy_id="native-runtime-state-api",
        available=bool(zone_mass_setters or state_methods),
        verified=False,
        evidence=(
            "candidate setters/state methods exposed by contamxpy: "
            + ",".join(zone_mass_setters + state_methods)
            if zone_mass_setters or state_methods
            else "no zone contaminant setter or generic state setter detected"
        ),
    )
    mass_adjustment = ContinuationStrategy(
        strategy_id="native-zone-mass-adjustment",
        available=bool(zone_mass_adjusters),
        verified=False,
        evidence=(
            "candidate zone contaminant mass-adjustment methods exposed by contamxpy: "
            + ",".join(zone_mass_adjusters)
            + "; semantics and continuity equivalence are not yet verified"
            if zone_mass_adjusters
            else "no zone contaminant mass-adjustment method detected"
        ),
    )
    restart = ContinuationStrategy(
        strategy_id="native-contam-restart",
        available=bool(restart_methods),
        verified=False,
        evidence=(
            "restart-like methods exposed by contamxpy: "
            + ",".join(restart_methods)
            if restart_methods
            else "CONTAM supports restart files, but no restart-like binding method was detected"
        ),
    )
    prj_reseed = ContinuationStrategy(
        strategy_id="prj-contaminant-reseed",
        available=bool(zone_mass_getters),
        verified=False,
        evidence=(
            "solved zone mass fractions are readable and AirTrajectory can serialize "
            "initial zone concentrations; full state equivalence remains unverified"
            if zone_mass_getters
            else "solved zone contaminant state is not readable through detected methods"
        ),
    )

    strategies = [
        native_runtime.as_dict(),
        mass_adjustment.as_dict(),
        restart.as_dict(),
        prj_reseed.as_dict(),
    ]
    payload = {
        "schema_version": "0.1",
        "probe": "contam-continuation-capability-v1",
        "engine_type": type(engine).__name__,
        "engine_module": type(engine).__module__,
        "callable_count": len(callables),
        "interesting_callables": _matching_names(callables),
        "zone_mass_getters": zone_mass_getters,
        "zone_mass_setters": zone_mass_setters,
        "zone_mass_adjusters": zone_mass_adjusters,
        "restart_methods": restart_methods,
        "state_methods": state_methods,
        "strategies": strategies,
        "state_reinjection_verified": False,
        "continuity_test_required": (
            "compare continuous two-step run against one-step + continuation + one-step "
            "for CO2, path flow, opening state, and time continuity"
        ),
    }
    return {
        **payload,
        "probe_sha256": _sha256(payload),
    }


def probe_contamxpy_engine(prj_path: str | Path) -> dict[str, Any]:
    from contamxpy import cxLib

    engine = cxLib(str(Path(prj_path)), 0, True, None)
    started = False
    try:
        status = engine.setupSimulation(1)
        if status not in (None, 0):
            raise RuntimeError(
                f"ContamX setupSimulation failed with status {status}"
            )
        started = True
        payload = classify_continuation_surface(engine)
        return {
            **payload,
            "contam_version": (
                engine.getVersion()
                if hasattr(engine, "getVersion")
                else "unknown"
            ),
            "zones": getattr(engine, "nZones", None),
            "paths": getattr(engine, "nPaths", None),
        }
    finally:
        if started:
            engine.endSimulation()


def compare_continuation_observations(
    *,
    continuous: dict[str, Any],
    resumed: dict[str, Any],
    co2_tolerance_ppm: float = 1.0,
    flow_tolerance_kg_s: float = 1e-6,
    opening_tolerance_pct: float = 1e-6,
) -> dict[str, Any]:
    """Compare the physical end state of continuous and resumed runs.

    This receipt is method-agnostic: native setters, restart files, and PRJ
    re-seeding can all be tested against the same acceptance contract.
    """
    if co2_tolerance_ppm < 0 or flow_tolerance_kg_s < 0 or opening_tolerance_pct < 0:
        raise ValueError("continuation tolerances must be non-negative")

    def mapping(name: str, row: dict[str, Any]) -> dict[str, float]:
        value = row.get(name)
        if not isinstance(value, dict):
            raise ValueError(f"{name} must be a mapping")
        return {str(key): float(raw) for key, raw in value.items()}

    continuous_co2 = mapping("co2_ppm", continuous)
    resumed_co2 = mapping("co2_ppm", resumed)
    continuous_flows = mapping("path_flow_kg_s", continuous)
    resumed_flows = mapping("path_flow_kg_s", resumed)
    continuous_openings = mapping("opening_pct", continuous)
    resumed_openings = mapping("opening_pct", resumed)

    if set(continuous_co2) != set(resumed_co2):
        raise ValueError("continuation CO2 zone sets differ")
    if set(continuous_flows) != set(resumed_flows):
        raise ValueError("continuation path-flow sets differ")
    if set(continuous_openings) != set(resumed_openings):
        raise ValueError("continuation opening sets differ")

    co2_error = {
        key: abs(continuous_co2[key] - resumed_co2[key])
        for key in sorted(continuous_co2)
    }
    flow_error = {
        key: abs(continuous_flows[key] - resumed_flows[key])
        for key in sorted(continuous_flows)
    }
    opening_error = {
        key: abs(continuous_openings[key] - resumed_openings[key])
        for key in sorted(continuous_openings)
    }

    continuous_time = continuous.get("simulation_time")
    resumed_time = resumed.get("simulation_time")
    time_continuity = (
        continuous_time == resumed_time
        if continuous_time is not None or resumed_time is not None
        else None
    )

    checks = {
        "co2_within_tolerance": all(
            value <= co2_tolerance_ppm for value in co2_error.values()
        ),
        "flow_within_tolerance": all(
            value <= flow_tolerance_kg_s for value in flow_error.values()
        ),
        "opening_within_tolerance": all(
            value <= opening_tolerance_pct for value in opening_error.values()
        ),
        "time_continuity": time_continuity,
    }
    comparable_time_pass = True if time_continuity is None else bool(time_continuity)
    passed = (
        checks["co2_within_tolerance"]
        and checks["flow_within_tolerance"]
        and checks["opening_within_tolerance"]
        and comparable_time_pass
    )

    payload = {
        "schema_version": "0.1",
        "comparison": "contam-continuation-equivalence-v1",
        "status": "PASS" if passed else "FAIL",
        "tolerances": {
            "co2_ppm": float(co2_tolerance_ppm),
            "path_flow_kg_s": float(flow_tolerance_kg_s),
            "opening_pct": float(opening_tolerance_pct),
        },
        "errors": {
            "co2_ppm": co2_error,
            "path_flow_kg_s": flow_error,
            "opening_pct": opening_error,
        },
        "checks": checks,
        "state_reinjection_verified": bool(passed),
    }
    return {
        **payload,
        "comparison_sha256": _sha256(payload),
    }
