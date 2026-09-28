"""Independent verification of persisted physical tau0 artifacts.

This module never contacts hardware and never creates evidence. It re-checks
that trajectory, audit receipt, commissioning bundle, ThingModel lineage and
sensor provenance still form one internally consistent chain.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .commissioning import (
    require_commissioning_behavior,
    validate_commissioning_behavior_context,
)
from .sensor_lineage import validate_sensor_evidence_context
from .lineage import (
    compare_hardware_site_lineage,
    compare_hardware_thingmodel_lineage,
    is_sha256,
    require_hardware_site_lineage,
    require_hardware_thingmodel_lineage,
    sensor_binding_matches_site,
    sensor_binding_valid,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path):
    payload=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload,dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _load_trajectory_record(path: Path, trajectory_id: str):
    matches=[]
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload=json.loads(line)
        if isinstance(payload,dict) and payload.get("id")==trajectory_id:
            matches.append(payload)
    if not matches:
        raise ValueError(f"trajectory id not found in {path}: {trajectory_id}")
    if len(matches)!=1:
        raise ValueError(f"trajectory id appears multiple times in {path}: {trajectory_id}")
    return matches[0]


def _check_sensor_rows(rows, *, step_index, phase, reasons, site_lineage):
    by_type={
        item.get("sensor_type"):item
        for item in rows
        if isinstance(item,dict)
    }
    for sensor_type,label in (("co2","CO2"),("rain","rain")):
        item=by_type.get(sensor_type)
        if item is None:
            reasons.append(f"step {step_index} missing {phase}{label} evidence")
            continue
        provenance=item.get("provenance")
        if not sensor_binding_valid(provenance):
            reasons.append(
                f"step {step_index} {phase}{label} evidence missing valid ThingModel/site provenance"
            )
        elif not sensor_binding_matches_site(provenance,site_lineage):
            reasons.append(
                f"step {step_index} {phase}{label} evidence belongs to a different physical site contract"
            )


def verify_physical_tau0_artifacts(*, trajectory_path, receipt_path, commission_bundle_path):
    trajectory_path=Path(trajectory_path)
    receipt_path=Path(receipt_path)
    commission_bundle_path=Path(commission_bundle_path)
    reasons=[]

    for label,path in (
        ("trajectory",trajectory_path),
        ("receipt",receipt_path),
        ("commissioning bundle",commission_bundle_path),
    ):
        if not path.exists():
            reasons.append(f"{label} file does not exist: {path}")
    if reasons:
        return {"valid_artifacts":False,"reasons":reasons}

    try:
        receipt=_load_json(receipt_path)
    except Exception as exc:
        return {"valid_artifacts":False,"reasons":[f"cannot read tau0 receipt: {exc}"]}

    if receipt.get("valid_tau0") is not True:
        reasons.append("tau0 receipt does not declare valid_tau0=true")
    if receipt.get("environment_kind")!="physical":
        reasons.append("tau0 receipt environment_kind is not physical")

    receipt_capture_policy=receipt.get("tau0_capture_policy")
    capture_target=None
    capture_start_tolerance=None
    capture_min_delta=None
    if not isinstance(receipt_capture_policy,dict):
        reasons.append("tau0 receipt missing capture policy")
    else:
        if receipt_capture_policy.get("policy_id")!="physical-tau0-probe-v1":
            reasons.append("tau0 receipt capture policy is not physical-tau0-probe-v1")
        try:
            capture_target=float(receipt_capture_policy.get("target_pct"))
            max_target=float(receipt_capture_policy.get("max_target_pct"))
            capture_start_tolerance=float(receipt_capture_policy.get("start_tolerance_pct"))
            capture_min_delta=float(receipt_capture_policy.get("minimum_reality_delta_pct"))
            if not 0 < capture_target <= 5.0:
                reasons.append("tau0 receipt capture target must be >0 and <=5%")
            if max_target != 5.0:
                reasons.append("tau0 receipt max target must remain 5%")
            if not 0 <= capture_start_tolerance <= 1.0:
                reasons.append("tau0 receipt start tolerance must be in [0,1]%")
            if not 0 < capture_min_delta <= capture_target:
                reasons.append("tau0 receipt minimum Reality Delta must be >0 and <= target")
            if int(receipt_capture_policy.get("steps") or 0)!=2:
                reasons.append("tau0 receipt capture policy must require exactly two steps")
            if receipt_capture_policy.get("requires_final_closed") is not True:
                reasons.append("tau0 receipt capture policy must require final closed state")
        except (TypeError,ValueError):
            reasons.append("tau0 receipt capture policy has invalid numeric fields")

    trajectory_sha=_sha256(trajectory_path)
    receipt_sha=_sha256(receipt_path)
    commission_sha=_sha256(commission_bundle_path)

    expected_trajectory_sha=str(receipt.get("trajectory_sha256") or "")
    expected_commission_sha=str(receipt.get("commissioning_bundle_sha256") or "")
    if not is_sha256(expected_trajectory_sha):
        reasons.append("tau0 receipt has invalid trajectory SHA-256")
    elif trajectory_sha!=expected_trajectory_sha:
        reasons.append("trajectory file SHA-256 does not match tau0 receipt")
    if not is_sha256(expected_commission_sha):
        reasons.append("tau0 receipt has invalid commissioning bundle SHA-256")
    elif commission_sha!=expected_commission_sha:
        reasons.append("commissioning bundle SHA-256 does not match tau0 receipt")

    receipt_behavior_witness=receipt.get("commissioning_behavior_witness")
    receipt_behavior_sha=str(receipt.get("commissioning_behavior_sha256") or "")
    try:
        validate_commissioning_behavior_context(
            receipt_behavior_witness,
            receipt_behavior_sha,
        )
    except RuntimeError as exc:
        reasons.append(str(exc))

    commissioning_id=str(receipt.get("commissioning_identity_sha256") or "")
    commissioning_identity=receipt.get("commissioning_hardware_identity") or {}
    runtime_identity=receipt.get("runtime_hardware_identity") or {}
    runtime_id=runtime_identity.get("identity_sha256") if isinstance(runtime_identity,dict) else None
    preflight_id=str(receipt.get("preflight_hardware_identity_sha256") or "")
    preflight_receipt_sha=str(receipt.get("preflight_receipt_sha256") or "")
    gateway_contract_sha=str(receipt.get("gateway_contract_sha256") or "")

    if not commissioning_id:
        reasons.append("tau0 receipt missing commissioning hardware identity")
    if not isinstance(commissioning_identity,dict) or commissioning_identity.get("identity_sha256")!=commissioning_id:
        reasons.append("tau0 receipt commissioning hardware identity payload mismatch")
    if runtime_id!=commissioning_id:
        reasons.append("runtime hardware identity does not match commissioning identity")
    if preflight_id!=commissioning_id:
        reasons.append("preflight hardware identity does not match commissioning identity")
    if not is_sha256(preflight_receipt_sha):
        reasons.append("tau0 receipt has invalid preflight receipt SHA-256")
    if not is_sha256(gateway_contract_sha):
        reasons.append("tau0 receipt has invalid gateway contract SHA-256")

    expected_lineage=None
    try:
        expected_lineage=require_hardware_thingmodel_lineage(
            commissioning_identity,
            label="commissioning hardware identity",
        )
        compare_hardware_thingmodel_lineage(
            commissioning_identity,
            runtime_identity,
            label="runtime",
        )
        if receipt.get("thingmodel_lineage")!=expected_lineage:
            reasons.append("tau0 receipt ThingModel lineage does not match hardware identities")
    except RuntimeError as exc:
        reasons.append(str(exc))

    expected_site_lineage=None
    try:
        expected_site_lineage=require_hardware_site_lineage(
            commissioning_identity,
            label="commissioning hardware identity",
        )
        compare_hardware_site_lineage(
            commissioning_identity,
            runtime_identity,
            label="runtime",
        )
        if receipt.get("site_lineage")!=expected_site_lineage:
            reasons.append("tau0 receipt physical-site lineage does not match hardware identities")
    except RuntimeError as exc:
        reasons.append(str(exc))

    receipt_sensor_fields={
        "sensor_evidence_origin":receipt.get("sensor_evidence_origin"),
        "runtime_sensor_lineage":receipt.get("runtime_sensor_lineage"),
        "sensor_staging_lineage":receipt.get("sensor_staging_lineage"),
        "sensor_evidence_sha256":receipt.get("sensor_evidence_sha256"),
    }
    receipt_has_sensor_lineage=any(
        value is not None for value in receipt_sensor_fields.values()
    )
    if receipt_has_sensor_lineage:
        try:
            validate_sensor_evidence_context(
                sensor_evidence_origin=receipt_sensor_fields["sensor_evidence_origin"],
                runtime_sensor_lineage=receipt_sensor_fields["runtime_sensor_lineage"],
                sensor_staging_lineage=receipt_sensor_fields["sensor_staging_lineage"],
                sensor_evidence_sha256=receipt_sensor_fields["sensor_evidence_sha256"],
                site_lineage=expected_site_lineage or {},
                commissioning_identity_sha256=commissioning_id,
                commissioning_bundle_sha256=expected_commission_sha,
            )
        except RuntimeError as exc:
            reasons.append(str(exc))

    bundle={}
    try:
        bundle=_load_json(commission_bundle_path)
        if bundle.get("status")!="PASS":
            reasons.append("commissioning bundle status is not PASS")

        try:
            bundle_behavior=require_commissioning_behavior(bundle)
            if bundle_behavior["sha256"]!=receipt_behavior_sha:
                reasons.append(
                    "commissioning behavior SHA-256 does not match tau0 receipt"
                )
            if bundle_behavior["normalized"]!=receipt_behavior_witness:
                reasons.append(
                    "commissioning behavior witness does not match tau0 receipt"
                )
        except RuntimeError as exc:
            reasons.append(str(exc))

        bundle_identity=bundle.get("hardware_identity") or {}
        bundle_id=bundle_identity.get("identity_sha256")
        if bundle_id!=commissioning_id:
            reasons.append("commissioning bundle hardware identity does not match tau0 receipt")
        try:
            bundle_lineage=require_hardware_thingmodel_lineage(
                bundle_identity,
                label="commissioning bundle hardware identity",
            )
            if expected_lineage is not None and bundle_lineage!=expected_lineage:
                reasons.append("commissioning bundle ThingModel lineage mismatch")
        except RuntimeError as exc:
            reasons.append(str(exc))
        try:
            bundle_site_lineage=require_hardware_site_lineage(
                bundle_identity,
                label="commissioning bundle hardware identity",
            )
            if (
                expected_site_lineage is not None
                and bundle_site_lineage!=expected_site_lineage
            ):
                reasons.append("commissioning bundle physical-site lineage mismatch")
        except RuntimeError as exc:
            reasons.append(str(exc))

        lineage=bundle.get("preflight") or {}
        if lineage.get("receipt_sha256")!=preflight_receipt_sha:
            reasons.append("commissioning bundle preflight receipt lineage mismatch")
        if lineage.get("hardware_identity_sha256")!=preflight_id:
            reasons.append("commissioning bundle preflight hardware identity mismatch")
        if lineage.get("gateway_contract_sha256")!=gateway_contract_sha:
            reasons.append("commissioning bundle gateway contract lineage mismatch")
    except Exception as exc:
        reasons.append(f"cannot validate commissioning bundle: {exc}")

    trajectory_id=str(receipt.get("trajectory_id") or "")
    if not trajectory_id:
        reasons.append("tau0 receipt missing trajectory_id")
    else:
        try:
            trajectory=_load_trajectory_record(trajectory_path,trajectory_id)
            if trajectory.get("environment_kind")!="physical":
                reasons.append("persisted trajectory environment_kind is not physical")

            context=trajectory.get("context") or {}
            if context.get("tau0_capture_policy")!=receipt_capture_policy:
                reasons.append("trajectory tau0 capture policy does not match receipt")

            reset_info=context.get("reset_info") or {}
            initial_feedback=reset_info.get("initial_position_feedback")
            initial_position=None
            if not isinstance(initial_feedback,dict):
                reasons.append("trajectory missing measured pre-action position feedback")
            elif initial_feedback.get("measured_position_pct") is None:
                reasons.append("trajectory pre-action position is not measured")
            else:
                try:
                    initial_position=float(initial_feedback.get("measured_position_pct"))
                    if (
                        capture_start_tolerance is not None
                        and initial_position > capture_start_tolerance
                    ):
                        reasons.append("trajectory pre-action position is not near closed")
                except (TypeError,ValueError):
                    reasons.append("trajectory pre-action measured position is invalid")

            if context.get("commissioning_identity_sha256")!=commissioning_id:
                reasons.append("trajectory commissioning identity lineage mismatch")
            if context.get("commissioning_hardware_identity")!=commissioning_identity:
                reasons.append("trajectory commissioning hardware identity payload mismatch")
            traj_runtime=context.get("runtime_hardware_identity") or {}
            if not isinstance(traj_runtime,dict) or traj_runtime.get("identity_sha256")!=runtime_id:
                reasons.append("trajectory runtime hardware identity lineage mismatch")
            if context.get("thingmodel_lineage")!=expected_lineage:
                reasons.append("trajectory ThingModel lineage mismatch")
            if context.get("site_lineage")!=expected_site_lineage:
                reasons.append("trajectory physical-site lineage mismatch")
            if context.get("commissioning_bundle_sha256")!=expected_commission_sha:
                reasons.append("trajectory commissioning bundle lineage mismatch")
            if context.get("preflight_receipt_sha256")!=preflight_receipt_sha:
                reasons.append("trajectory preflight receipt lineage mismatch")
            if context.get("preflight_hardware_identity_sha256")!=preflight_id:
                reasons.append("trajectory preflight hardware identity lineage mismatch")
            if context.get("gateway_contract_sha256")!=gateway_contract_sha:
                reasons.append("trajectory gateway contract lineage mismatch")
            if context.get("commissioning_behavior_sha256")!=receipt_behavior_sha:
                reasons.append("trajectory commissioning behavior hash mismatch")
            if context.get("commissioning_behavior_witness")!=receipt_behavior_witness:
                reasons.append("trajectory commissioning behavior witness mismatch")
            try:
                validate_commissioning_behavior_context(
                    context.get("commissioning_behavior_witness"),
                    context.get("commissioning_behavior_sha256"),
                )
            except RuntimeError as exc:
                reasons.append(str(exc))

            trajectory_sensor_fields={
                "sensor_evidence_origin":context.get("sensor_evidence_origin"),
                "runtime_sensor_lineage":context.get("runtime_sensor_lineage"),
                "sensor_staging_lineage":context.get("sensor_staging_lineage"),
                "sensor_evidence_sha256":context.get("sensor_evidence_sha256"),
            }
            trajectory_has_sensor_lineage=any(
                value is not None
                for value in trajectory_sensor_fields.values()
            )
            if trajectory_has_sensor_lineage != receipt_has_sensor_lineage:
                reasons.append(
                    "trajectory/tau0 receipt sensor evidence presence mismatch"
                )
            elif trajectory_has_sensor_lineage:
                for key,value in receipt_sensor_fields.items():
                    if trajectory_sensor_fields.get(key)!=value:
                        reasons.append(
                            f"trajectory {key} does not match tau0 receipt"
                        )
                try:
                    validate_sensor_evidence_context(
                        sensor_evidence_origin=trajectory_sensor_fields["sensor_evidence_origin"],
                        runtime_sensor_lineage=trajectory_sensor_fields["runtime_sensor_lineage"],
                        sensor_staging_lineage=trajectory_sensor_fields["sensor_staging_lineage"],
                        sensor_evidence_sha256=trajectory_sensor_fields["sensor_evidence_sha256"],
                        site_lineage=expected_site_lineage or {},
                        commissioning_identity_sha256=commissioning_id,
                        commissioning_bundle_sha256=expected_commission_sha,
                    )
                except RuntimeError as exc:
                    reasons.append(str(exc))

            steps=trajectory.get("steps") or []
            if len(steps)!=int(receipt.get("steps") or 0):
                reasons.append("persisted trajectory step count does not match tau0 receipt")
            if not steps:
                reasons.append("persisted trajectory has no steps")
            if len(steps)!=2:
                reasons.append("persisted physical tau0 must contain exactly two steps")

            max_measured_delta=0.0
            reality_delta_observed=False
            final_measured_position=None
            for index,step in enumerate(steps):
                actions=list(step.get("proposed_actions") or [])+list(step.get("executed_actions") or [])
                for action in actions:
                    if not isinstance(action,dict):
                        continue
                    try:
                        target=float(action.get("target_pct"))
                    except (TypeError,ValueError):
                        reasons.append(f"step {index} has invalid tau0 action target")
                        continue
                    if target < 0 or target > 5.0:
                        reasons.append(f"step {index} exceeds bounded tau0 target")

                executed=[
                    item for item in (step.get("executed_actions") or [])
                    if isinstance(item,dict)
                ]
                expected_target=capture_target if index==0 else 0.0
                if executed and expected_target is not None:
                    for action in executed:
                        try:
                            actual=float(action.get("target_pct"))
                        except (TypeError,ValueError):
                            continue
                        if abs(actual-float(expected_target))>1e-9:
                            reasons.append(
                                f"step {index} tau0 target sequence mismatch; "
                                f"expected {float(expected_target):.1f}%"
                            )

                pre_rows=[
                    item for item in (step.get("sensor_readings") or [])
                    if isinstance(item,dict)
                ]
                _check_sensor_rows(
                    pre_rows,
                    step_index=index,
                    phase="",
                    reasons=reasons,
                    site_lineage=expected_site_lineage or {},
                )

                feedback=[
                    item for item in (step.get("actuator_feedback") or [])
                    if isinstance(item,dict)
                ]
                if not feedback:
                    reasons.append(f"step {index} missing actuator feedback")
                    feedback_ts=None
                else:
                    if any(item.get("measured_position_pct") is None for item in feedback):
                        reasons.append(f"step {index} lacks measured actuator position")
                    timestamps=[float(item.get("timestamp") or 0) for item in feedback]
                    if any(ts<=0 for ts in timestamps):
                        reasons.append(f"step {index} actuator feedback missing timestamp")
                    feedback_ts=max(timestamps) if timestamps else None
                    if initial_position is not None:
                        for item in feedback:
                            measured=item.get("measured_position_pct")
                            if measured is None:
                                continue
                            delta=abs(float(measured)-initial_position)
                            max_measured_delta=max(max_measured_delta,delta)
                            if (
                                capture_min_delta is not None
                                and delta >= capture_min_delta
                            ):
                                reality_delta_observed=True
                            if index==len(steps)-1:
                                final_measured_position=float(measured)

                post_rows=[
                    item for item in (step.get("next_sensor_readings") or [])
                    if isinstance(item,dict)
                ]
                _check_sensor_rows(
                    post_rows,
                    step_index=index,
                    phase="post-action ",
                    reasons=reasons,
                    site_lineage=expected_site_lineage or {},
                )
                if feedback_ts is not None:
                    for item in post_rows:
                        if item.get("sensor_type") in ("co2","rain"):
                            if float(item.get("timestamp") or 0)<=feedback_ts:
                                reasons.append(
                                    f"step {index} post-action sensor evidence is not newer than actuator feedback"
                                )
                                break

            if not reality_delta_observed:
                detail=(
                    f" (max {max_measured_delta:.3f}%)"
                    if initial_position is not None else ""
                )
                reasons.append(
                    "persisted physical tau0 has no required measured Reality Delta"+detail
                )
            if final_measured_position is None:
                reasons.append("persisted physical tau0 missing final measured closeout position")
            elif (
                capture_start_tolerance is not None
                and final_measured_position > capture_start_tolerance
            ):
                reasons.append(
                    "persisted physical tau0 did not restore closed state; "
                    f"final {final_measured_position:.3f}%"
                )
        except Exception as exc:
            reasons.append(f"cannot validate persisted trajectory: {exc}")

    return {
        "valid_artifacts":not reasons,
        "reasons":reasons,
        "trajectory_id":trajectory_id or None,
        "trajectory_sha256":trajectory_sha,
        "receipt_sha256":receipt_sha,
        "commissioning_bundle_sha256":commission_sha,
        "commissioning_identity_sha256":commissioning_id or None,
        "runtime_hardware_identity_sha256":runtime_id,
        "thingmodel_lineage":expected_lineage,
        "site_lineage":expected_site_lineage,
        "preflight_receipt_sha256":preflight_receipt_sha or None,
        "gateway_contract_sha256":gateway_contract_sha or None,
        "commissioning_behavior_sha256":receipt_behavior_sha or None,
        "tau0_capture_policy":receipt_capture_policy,
        "sensor_evidence_origin":receipt_sensor_fields["sensor_evidence_origin"],
        "sensor_evidence_sha256":receipt_sensor_fields["sensor_evidence_sha256"],
    }
