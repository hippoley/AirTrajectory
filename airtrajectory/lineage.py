"""Portable hardware, ThingModel and physical-site evidence-lineage helpers.

AirTrajectory does not embed private vendor registries or deployment manifests.
It requires the commissioned WindowPilot runtime to emit non-secret identity
fields and cryptographic digests, then verifies the same lineage survives
commissioning, runtime, trajectory, dataset and persisted artifacts.
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

SITE_IDENTITY_FIELDS=(
    "site_id",
    "room_id",
    "device_instance_id",
    "site_device_id",
    "site_product_model",
    "site_product_key",
    "site_manifest_sha256",
    "site_instance_contract_sha256",
    "site_contract_sha256",
)
SITE_HASH_FIELDS=(
    "site_manifest_sha256",
    "site_instance_contract_sha256",
    "site_contract_sha256",
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
    "site_id",
    "site_instance_id",
    "site_manifest_sha256",
    "site_contract_sha256",
)
SENSOR_HASH_FIELDS=(
    "source_sha256",
    "source_bundle_sha256",
    "registry_sha256",
    "contract_sha256",
    "site_manifest_sha256",
    "site_contract_sha256",
)


def is_sha256(value) -> bool:
    text=str(value or "")
    return len(text)==64 and all(ch in "0123456789abcdefABCDEF" for ch in text)


def _require_lineage(identity, fields, hash_fields, *, label, kind):
    if not isinstance(identity,dict):
        raise RuntimeError(f"{label} is missing")
    lineage={}
    for key in fields:
        value=identity.get(key)
        if value in (None,""):
            raise RuntimeError(f"{label} missing {key}")
        if key in hash_fields and not is_sha256(value):
            raise RuntimeError(f"{label} has invalid {key}")
        lineage[key]=value
    return lineage


def require_hardware_thingmodel_lineage(identity, *, label="hardware identity") -> dict:
    return _require_lineage(
        identity,
        THINGMODEL_IDENTITY_FIELDS,
        THINGMODEL_HASH_FIELDS,
        label=label,
        kind="ThingModel",
    )


def compare_hardware_thingmodel_lineage(expected, actual, *, label="runtime") -> dict:
    left=require_hardware_thingmodel_lineage(
        expected,
        label="commissioning hardware identity",
    )
    right=require_hardware_thingmodel_lineage(
        actual,
        label=f"{label} hardware identity",
    )
    mismatched=[key for key in THINGMODEL_IDENTITY_FIELDS if left[key]!=right[key]]
    if mismatched:
        raise RuntimeError(
            f"{label} ThingModel lineage does not match commissioning: "
            +",".join(mismatched)
        )
    return left


def require_hardware_site_lineage(identity, *, label="hardware identity") -> dict:
    lineage=_require_lineage(
        identity,
        SITE_IDENTITY_FIELDS,
        SITE_HASH_FIELDS,
        label=label,
        kind="site",
    )
    if lineage["site_device_id"] != identity.get("device_id"):
        raise RuntimeError(f"{label} site_device_id does not match device_id")
    if lineage["site_product_model"] != identity.get("thingmodel_product_model"):
        raise RuntimeError(
            f"{label} site_product_model does not match ThingModel product model"
        )
    if lineage["site_product_key"] != identity.get("thingmodel_product_key"):
        raise RuntimeError(
            f"{label} site_product_key does not match ThingModel productKey"
        )
    return lineage


def compare_hardware_site_lineage(expected, actual, *, label="runtime") -> dict:
    left=require_hardware_site_lineage(
        expected,
        label="commissioning hardware identity",
    )
    right=require_hardware_site_lineage(
        actual,
        label=f"{label} hardware identity",
    )
    mismatched=[key for key in SITE_IDENTITY_FIELDS if left[key]!=right[key]]
    if mismatched:
        raise RuntimeError(
            f"{label} physical-site lineage does not match commissioning: "
            +",".join(mismatched)
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
