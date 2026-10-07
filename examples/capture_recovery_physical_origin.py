"""Capture a fresh read-only physical origin after lease recovery."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from airtrajectory.drivers import WindowPilotHTTPDriver
from airtrajectory.physical_origin_lease import (
    bind_recovery_origin_to_execution_lease,
)
from airtrajectory.physical_origin_recovery import (
    capture_recovery_physical_origin,
)


def _write(path, payload):
    target=Path(path)
    target.parent.mkdir(parents=True,exist_ok=True)
    temp=target.with_suffix(target.suffix+".tmp")
    temp.write_text(
        json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+"\n",
        encoding="utf-8",
    )
    temp.replace(target)


def run_recovery_capture(
    *,
    driver,
    previous_origin,
    lease,
    opening_id,
    zone_id,
    out,
    max_observation_age_s=10.0,
    clock_fn=time.time,
):
    previous_payload=json.loads(
        Path(previous_origin).read_text(encoding="utf-8")
    )
    receipt=capture_recovery_physical_origin(
        driver=driver,
        previous_origin_receipt=previous_payload,
        lease_path=lease,
        opening_id=opening_id,
        zone_id=zone_id,
        max_observation_age_s=max_observation_age_s,
        clock_fn=clock_fn,
    )

    # Persist the fresh origin before binding the old lease to it. If the write
    # fails, the lease remains RECOVERY_REQUIRED and no false recovery is
    # recorded.
    _write(out,receipt)

    lease_result=bind_recovery_origin_to_execution_lease(
        lease_path=lease,
        recovery_origin_receipt=receipt,
        bound_at=max(float(clock_fn()),1e-9),
    )
    return {
        "schema_version":"0.1",
        "workflow":"read-only-physical-origin-recovery-v1",
        "status":"RECOVERED",
        "motion_performed":False,
        "recovery_origin":str(out),
        "recovery_origin_sha256":receipt["origin_sha256"],
        "recovery_origin_receipt_sha256":receipt[
            "physical_origin_receipt_sha256"
        ],
        "lease_sha256":lease_result["lease_sha256"],
        "evidence_boundary":(
            "read-only recovery from measured WindowPilot position and fresh "
            "CO2/rain; no actuator command is issued"
        ),
    }


def main(argv=None):
    parser=argparse.ArgumentParser(
        description=(
            "Capture a fresh read-only physical origin after a physical "
            "execution lease has been sealed RECOVERY_REQUIRED."
        )
    )
    parser.add_argument("--windowpilot",default="http://127.0.0.1:8001")
    parser.add_argument("--previous-origin",required=True)
    parser.add_argument("--lease",required=True)
    parser.add_argument("--opening-id",required=True)
    parser.add_argument("--zone-id",required=True)
    parser.add_argument(
        "--max-observation-age-s",
        type=float,
        default=10.0,
    )
    parser.add_argument(
        "--out",
        default="artifacts/recovery-physical-origin.json",
    )
    args=parser.parse_args(argv)

    result=run_recovery_capture(
        driver=WindowPilotHTTPDriver(args.windowpilot),
        previous_origin=args.previous_origin,
        lease=args.lease,
        opening_id=args.opening_id,
        zone_id=args.zone_id,
        out=args.out,
        max_observation_age_s=args.max_observation_age_s,
    )
    print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
