#!/usr/bin/env python3
"""Build governed operational history index from persisted snapshots."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def risk_from_trend(trend: dict[str, Any]) -> str:
    direction = trend.get("direction")
    if direction == "piorando":
        return "high"
    if direction == "estavel":
        return "medium_low"
    if direction == "melhorando":
        return "low"
    return "medium"


def build_index(
    repository: str,
    history: list[dict[str, Any]],
    trend: dict[str, Any],
    artifact_href: str,
) -> dict[str, Any]:
    snapshots = []
    for idx, item in enumerate(history[-50:]):
        snapshots.append(
            {
                "id": f"snapshot-{idx}",
                "generated_at": item.get("snapshot_at_utc") or datetime.now(timezone.utc).isoformat(),
                "source": "operational-center-history",
                "href": artifact_href,
                "status": item.get("hub_status", "unknown"),
                "hub_score": item.get("hub_score"),
            }
        )

    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repository": repository,
        "correlation_id": str(uuid4()),
        "retention_policy": {
            "artifact_retention_days": 60,
            "long_term_storage": "governed_index_report_only",
            "write_mode": "report_only",
        },
        "summary": {
            "snapshot_count": len(snapshots),
            "risk": risk_from_trend(trend),
            "maturity_percent": round(float(trend.get("last_score") or trend.get("avg_score") or 0), 2),
        },
        "snapshots": snapshots,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build governed operational history index.")
    parser.add_argument("--repository", default="local/reqsys")
    parser.add_argument(
        "--history",
        type=Path,
        default=Path("artifacts/operational-history/operational-history.json"),
    )
    parser.add_argument(
        "--trend",
        type=Path,
        default=Path("artifacts/operational-history/operational-history-trend.json"),
    )
    parser.add_argument(
        "--artifact-href",
        default="artifacts/operational-history/operational-history.json",
    )
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/operational-history-index"))
    args = parser.parse_args()

    history = load_json(args.history, [])
    if not isinstance(history, list):
        history = []
    trend = load_json(args.trend, {})
    index = build_index(args.repository, history, trend, args.artifact_href)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "operational-history-index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"snapshots={index['summary']['snapshot_count']} risk={index['summary']['risk']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
