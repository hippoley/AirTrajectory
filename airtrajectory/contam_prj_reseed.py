"""PRJ Section 15 contaminant-state re-seeding utilities.

This module performs a deliberately narrow edit: replace only the initial zone
concentration rows in an AirTrajectory-generated CONTAM PRJ. It does not alter
geometry, airflow elements, controls, weather, or simulation settings.
"""
from __future__ import annotations

import hashlib
import re
from typing import Mapping


_HEADER_RE = re.compile(r"^(?P<count>\d+)\s+!\s+initial zone concentrations:\s*$")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def reseed_initial_zone_mass_fractions(
    prj_text: str,
    zone_mass_fractions: Mapping[int, float],
) -> dict:
    if not isinstance(prj_text, str) or not prj_text:
        raise ValueError("prj_text must be non-empty")
    if not zone_mass_fractions:
        raise ValueError("zone_mass_fractions must not be empty")

    normalized = {int(k): float(v) for k, v in zone_mass_fractions.items()}
    if any(zone <= 0 for zone in normalized):
        raise ValueError("zone numbers must be positive")
    if any(value < 0 for value in normalized.values()):
        raise ValueError("mass fractions must be non-negative")

    lines = prj_text.splitlines()
    header_index = None
    expected_count = None
    for index, line in enumerate(lines):
        match = _HEADER_RE.match(line.strip())
        if match:
            header_index = index
            expected_count = int(match.group("count"))
            break
    if header_index is None or expected_count is None:
        raise ValueError("initial zone concentrations section not found")
    if expected_count != len(normalized):
        raise ValueError(
            f"zone mass-fraction count mismatch: PRJ expects {expected_count}, "
            f"got {len(normalized)}"
        )

    data_start = header_index + 2
    data_end = data_start + expected_count
    if data_end > len(lines):
        raise ValueError("initial zone concentrations section is truncated")

    seen = set()
    replacements = {}
    for index in range(data_start, data_end):
        row = lines[index].strip().split()
        if len(row) < 2:
            raise ValueError("invalid initial zone concentration row")
        zone_number = int(row[0])
        if zone_number in seen:
            raise ValueError(f"duplicate zone concentration row: {zone_number}")
        seen.add(zone_number)
        if zone_number not in normalized:
            raise ValueError(
                f"missing replacement mass fraction for zone {zone_number}"
            )
        original = float(row[1])
        replacement = normalized[zone_number]
        lines[index] = f"{zone_number:4d} {replacement:.8e}"
        replacements[str(zone_number)] = {
            "before_mass_fraction": original,
            "after_mass_fraction": replacement,
            "delta_mass_fraction": replacement - original,
        }

    if seen != set(normalized):
        extra = sorted(set(normalized) - seen)
        raise ValueError(f"replacement includes unknown zones: {extra}")

    rendered = "\n".join(lines) + ("\n" if prj_text.endswith("\n") else "")
    payload = {
        "schema_version": "0.1",
        "operation": "contam-prj-section15-reseed-v1",
        "source_prj_sha256": _sha256_text(prj_text),
        "reseeded_prj_sha256": _sha256_text(rendered),
        "zone_count": expected_count,
        "replacements": replacements,
    }
    return {
        "text": rendered,
        "receipt": payload,
    }
