"""Safely seal an abandoned physical-origin execution lease.

This command never reopens or replays the old physical origin. It only changes
an IN_FLIGHT lease to RECOVERY_REQUIRED when the original owner process can be
proven absent on the same host.
"""
from __future__ import annotations

import argparse
import json
import time

from airtrajectory.physical_origin_lease import (
    recover_abandoned_physical_origin_execution,
)


def main(argv=None):
    parser=argparse.ArgumentParser(
        description=(
            "Seal a dead-owner IN_FLIGHT physical-origin execution lease as "
            "RECOVERY_REQUIRED without issuing any hardware command."
        )
    )
    parser.add_argument("--lease",required=True)
    args=parser.parse_args(argv)

    result=recover_abandoned_physical_origin_execution(
        lease_path=args.lease,
        recovered_at=time.time(),
    )
    print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
