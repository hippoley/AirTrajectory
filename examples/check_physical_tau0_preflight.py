"""Zero-motion gate before an audited physical tau0 capture."""
import argparse
import json
import time
from pathlib import Path

from airtrajectory.drivers import WindowPilotHTTPDriver
from airtrajectory.tau0_preflight import validate_physical_tau0_preconditions


def check_physical_tau0_preflight(
    *,
    driver,
    commission_bundle,
    receipt,
    sensor_apply_receipts=None,
    now_fn=time.time,
):
    payload=validate_physical_tau0_preconditions(
        driver=driver,
        commission_bundle=commission_bundle,
        sensor_apply_receipts=sensor_apply_receipts,
    )
    payload={
        **payload,
        "checked_at":float(now_fn()),
        "next_gate":{
            "command":"python examples/capture_physical_tau0.py",
            "requires_same_commission_bundle":True,
            "requires_same_runtime_identity":True,
            "motion_allowed_after_pass":True,
        },
    }
    path=Path(receipt)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(
        json.dumps(payload,ensure_ascii=False,indent=2),
        encoding="utf-8",
    )
    return payload


def main(argv=None):
    parser=argparse.ArgumentParser(
        description="Read-only validation of every prerequisite for physical tau0"
    )
    parser.add_argument("--windowpilot",default="http://127.0.0.1:8000")
    parser.add_argument("--commission-bundle",required=True)
    parser.add_argument(
        "--sensor-apply-receipt",
        action="append",
        default=[],
        help=(
            "Optional WindowPilot sensor_apply PASS receipt. Supply exactly "
            "two (CO2 + rain) for probe-apply-audited sensor lineage."
        ),
    )
    parser.add_argument(
        "--receipt",
        default="artifacts/physical-tau0-preflight.json",
    )
    args=parser.parse_args(argv)

    payload=check_physical_tau0_preflight(
        driver=WindowPilotHTTPDriver(args.windowpilot),
        commission_bundle=args.commission_bundle,
        receipt=args.receipt,
        sensor_apply_receipts=args.sensor_apply_receipt,
    )
    print(json.dumps(payload,ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
