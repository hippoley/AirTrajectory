"""Re-verify persisted physical tau0 artifacts without contacting hardware."""
import argparse
import json

from airtrajectory.evidence import verify_physical_tau0_artifacts


def main(argv=None):
    parser=argparse.ArgumentParser(
        description="Verify trajectory + tau0 receipt + commissioning evidence lineage"
    )
    parser.add_argument("--trajectory",default="artifacts/physical-tau0.jsonl")
    parser.add_argument("--receipt",default="artifacts/physical-tau0-audit.json")
    parser.add_argument("--commission-bundle",required=True)
    args=parser.parse_args(argv)
    report=verify_physical_tau0_artifacts(
        trajectory_path=args.trajectory,
        receipt_path=args.receipt,
        commission_bundle_path=args.commission_bundle,
    )
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if report["valid_artifacts"] else 2


if __name__=="__main__":
    raise SystemExit(main())
