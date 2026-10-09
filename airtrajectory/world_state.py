"""Canonical, immutable *software* world snapshot with honest evidence class.

This contract does not attest physical provenance. E4 field measurements and
E5 independent adoption require an external verifier, not a caller-set flag.
No physical actuator may be authorized from this snapshot alone.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from math import isfinite
from typing import Any, Mapping

from .topology import BuildingTopology


_METRICS = {
    "co2_ppm", "pm25_ug_m3", "tvoc_ug_m3", "hcho_mg_m3",
    "temperature_c", "relative_humidity_pct",
}
_EVIDENCE_SOURCES = {
    "E1": {"contract-test", "fixture"},
    "E2": {"toy-simulator"},
    "E3": {"contamx", "public-ifc", "external-dataset-adapter"},
}


def _digest(payload: Any) -> tuple[bytes, str]:
    try:
        data = json.dumps(
            payload, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("world snapshot must be finite canonical JSON") from exc
    return data, hashlib.sha256(data).hexdigest()


def _number(value: Any, label: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"{label} must be finite numeric")
    number = float(value)
    if minimum is not None and number < minimum:
        raise ValueError(f"{label} must be >= {minimum}")
    return number


@dataclass(frozen=True)
class EvidenceRef:
    level: str
    source_type: str
    source_id: str
    backend: str | None = None
    receipt_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.level not in _EVIDENCE_SOURCES:
            raise ValueError("self-asserted E4/E5 or unknown evidence level is prohibited")
        if self.source_type not in _EVIDENCE_SOURCES[self.level]:
            raise ValueError("evidence source and level disagree")
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise ValueError("evidence source_id required")
        if self.level == "E3":
            if not isinstance(self.backend, str) or not self.backend.strip():
                raise ValueError("E3 backend identifier required")
            if not isinstance(self.receipt_sha256, str) or (
                len(self.receipt_sha256) != 64
                or any(c not in "0123456789abcdef" for c in self.receipt_sha256)
            ):
                raise ValueError("E3 source receipt SHA-256 required")
        # A SHA only binds bytes; it is not independent authenticity proof.

    def as_dict(self) -> dict[str, Any]:
        return {
            "level": self.level, "source_type": self.source_type,
            "source_id": self.source_id, "backend": self.backend,
            "receipt_sha256": self.receipt_sha256,
            "field_measurement_verified": False,
            "independent_adoption_verified": False,
        }


@dataclass(frozen=True)
class CanonicalWorldState:
    """Store immutable canonical bytes so external nested dict edits cannot drift."""

    canonical_json: bytes
    sha256: str

    @classmethod
    def from_parts(
        cls,
        *,
        topology: BuildingTopology,
        opening_pct: Mapping[str, float],
        zone_environment: Mapping[str, Mapping[str, float | None]],
        rain: bool | None,
        observed_at: float,
        evidence: EvidenceRef,
        hardware_bindings: Mapping[str, str] | None = None,
        sensor_bindings: Mapping[str, str] | None = None,
    ) -> "CanonicalWorldState":
        topology.validate()
        if not isinstance(rain, (bool, type(None))):
            raise ValueError("rain must be true/false/unavailable")
        ts = _number(observed_at, "observed_at", minimum=0)
        if ts == 0:
            raise ValueError("observed_at must be positive")
        if set(opening_pct) != set(topology.openings):
            raise ValueError("world opening coverage must equal topology")
        openings = {}
        for opening_id, value in opening_pct.items():
            pct = _number(value, f"opening {opening_id}", minimum=0)
            if pct > 100:
                raise ValueError("opening percentage outside [0,100]")
            openings[opening_id] = pct
        if set(zone_environment) != set(topology.zones):
            raise ValueError("world environmental zone coverage must equal topology")
        environment: dict[str, dict[str, float | None]] = {}
        for zone_id, metrics in zone_environment.items():
            if not isinstance(metrics, Mapping) or not metrics:
                raise ValueError(f"zone {zone_id} needs explicit environment fields")
            unknown = set(metrics) - _METRICS
            if unknown:
                raise ValueError(f"unsupported environment fields: {sorted(unknown)}")
            fields: dict[str, float | None] = {}
            for name, value in metrics.items():
                if value is None:
                    fields[name] = None
                    continue
                number = _number(
                    value, f"{zone_id}:{name}",
                    minimum=None if name == "temperature_c" else 0,
                )
                if name == "relative_humidity_pct" and number > 100:
                    raise ValueError("relative humidity outside [0,100]")
                fields[name] = number
            environment[zone_id] = fields

        def bindings(value: Mapping[str, str] | None, label: str) -> dict[str, str]:
            result = dict(value or {})
            if set(result) - set(topology.openings if label == "hardware" else topology.zones):
                raise ValueError(f"{label} binding references unknown topology IDs")
            if any(not isinstance(v, str) or not v.strip() for v in result.values()):
                raise ValueError(f"{label} binding identifier must be nonempty")
            if len(set(result.values())) != len(result):
                raise ValueError(f"{label} binding identity collision")
            return result

        payload = {
            "schema_version": "0.1",
            "topology": {
                "outside_id": topology.outside_id,
                "zones": {
                    key: {"id": zone.id, "volume_m3": _number(zone.volume_m3, key, minimum=0), "kind": zone.kind}
                    for key, zone in topology.zones.items()
                },
                "openings": {
                    key: {
                        "id": edge.id, "source": edge.source, "target": edge.target,
                        "kind": edge.kind, "max_area_m2": _number(edge.max_area_m2, key, minimum=0),
                        "controllable": edge.controllable,
                    }
                    for key, edge in topology.openings.items()
                },
            },
            "opening_pct": openings,
            "zone_environment": environment,
            "rain": rain,
            "observed_at": ts,
            "hardware_bindings": bindings(hardware_bindings, "hardware"),
            "sensor_bindings": bindings(sensor_bindings, "sensor"),
            "evidence": evidence.as_dict(),
            "execution_authorized": False,
        }
        encoded, sha = _digest(payload)
        return cls(encoded, sha)

    def as_dict(self) -> dict[str, Any]:
        return json.loads(self.canonical_json)

    def assert_same_origin(self, expected_sha256: str) -> None:
        if self.sha256 != expected_sha256:
            raise RuntimeError("world origin changed; reject stale plan")

    def require_physical_authorization(self) -> None:
        raise RuntimeError(
            "software world state is not a physical authorization; "
            "use measured hardware lineage and the commissioned action gate"
        )
