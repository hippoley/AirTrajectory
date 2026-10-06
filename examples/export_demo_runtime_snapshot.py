"""Export the resolved demo runtime snapshot consumed by the browser."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.demo_runtime import DemoRuntimeSnapshot
from airtrajectory.layout import LayoutContract


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--layout",
        type=Path,
        default=Path("web/data/home_topology.fixed.json"),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("web/data/demo_runtime.generated.json"),
    )
    parser.add_argument("--topology-revision", type=int, default=0)
    args = parser.parse_args()

    layout = LayoutContract.from_file(args.layout)
    snapshot = DemoRuntimeSnapshot.resolve(
        layout,
        topology_revision=args.topology_revision,
    )
    payload = snapshot.web_payload()
    payload["runtime"]["source"] = "DemoRuntimeSnapshot"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "out": str(args.out),
                "topology_id": layout.topology_id,
                "topology_revision": snapshot.topology_revision,
                "snapshot_sha256": snapshot.sha256(),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
