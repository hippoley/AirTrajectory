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
