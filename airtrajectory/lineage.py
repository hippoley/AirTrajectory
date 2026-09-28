"""Portable ThingModel evidence-lineage helpers.

AirTrajectory intentionally does not embed the private/vendor registry. It only
requires cryptographic/product identity emitted by the commissioned runtime and
checks that the same lineage survives through runtime, trajectory and artifacts.
"""
from __future__ import annotations


THINGMODEL_IDENTITY_FIELDS=(
    "thingmodel_product_model",
    "thingmodel_product_key",
    "thingmodel_version",
    "thingmodel_source_sha256",
    "thingmodel_source_bundle_sha256",
    "thingmodel_registry_sha256",
    "thingmodel_contract_sha256",
)
THINGMODEL_HASH_FIELDS=(
    "thingmodel_source_sha256",
    "thingmodel_source_bundle_sha256",
    "thingmodel_registry_sha256",
    "thingmodel_contract_sha256",
)
SENSOR_BINDING_FIELDS=(
    "product_model",
    "product_key",
    "device_id",
    "property",
    "source_sha256",
    "source_bundle_sha256",
    "registry_sha256",
    "contract_sha256",
)
SENSOR_HASH_FIELDS=(
    "source_sha256",
    "source_bundle_sha256",
    "registry_sha256",
    "contract_sha256",
)


def is_sha256(value) -> bool:
    text=str(value or "")
    return len(text)==64 and all(ch in "0123456789abcdefABCDEF" for ch in text)


def require_hardware_thingmodel_lineage(identity, *, label="hardware identity") -> dict:
    if not isinstance(identity,dict):
        raise RuntimeError(f"{label} is missing")
    lineage={}
    for key in THINGMODEL_IDENTITY_FIELDS:
        value=identity.get(key)
        if value in (None,""):
            raise RuntimeError(f"{label} missing {key}")
        if key in THINGMODEL_HASH_FIELDS and not is_sha256(value):
            raise RuntimeError(f"{label} has invalid {key}")
        lineage[key]=value
    return lineage


def compare_hardware_thingmodel_lineage(expected, actual, *, label="runtime") -> dict:
    left=require_hardware_thingmodel_lineage(expected,label="commissioning hardware identity")
    right=require_hardware_thingmodel_lineage(actual,label=f"{label} hardware identity")
    mismatched=[key for key in THINGMODEL_IDENTITY_FIELDS if left[key]!=right[key]]
    if mismatched:
        raise RuntimeError(
            f"{label} ThingModel lineage does not match commissioning: "+",".join(mismatched)
        )
    return left


def sensor_binding_valid(provenance) -> bool:
    if not isinstance(provenance,dict):
        return False
    for key in SENSOR_BINDING_FIELDS:
        value=provenance.get(key)
        if value in (None,""):
            return False
        if key in SENSOR_HASH_FIELDS and not is_sha256(value):
            return False
    return True
