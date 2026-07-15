#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"
MAX_HISTORY = 30


def _load_list(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError(f"{path} deve conter uma lista JSON")
    return [item for item in value if isinstance(item, dict)]


def build_chain(
    previous: list[dict[str, Any]] | None,
    current: dict[str, Any],
    *,
    run_id: str,
    head_sha: str,
    source_workflow: str,
) -> list[dict[str, Any]]:
    if not run_id.strip():
        raise ValueError("run_id é obrigatório")
    if len(head_sha.strip()) < 7:
        raise ValueError("head_sha inválido")
    required = ("recovery_rate", "average_recovery_seconds", "ux_100_ready")
    missing = [name for name in required if name not in current]
    if missing:
        raise ValueError(f"evidência atual sem campos obrigatórios: {', '.join(missing)}")

    sample = {
        "schema_version": SCHEMA_VERSION,
        "source_workflow": source_workflow,
        "source_run_id": str(run_id),
        "source_head_sha": head_sha,
        "generated_at": current.get("generated_at") or datetime.now(timezone.utc).isoformat(),
        "recovery_rate": float(current["recovery_rate"]),
        "average_recovery_seconds": float(current["average_recovery_seconds"]),
        "ux_100_ready": current["ux_100_ready"] is True,
    }

    deduplicated: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for item in [*(previous or []), sample]:
        key = str(item.get("source_run_id") or f"legacy:{item.get('generated_at', len(order))}")
        if key not in deduplicated:
            order.append(key)
        deduplicated[key] = item

    return [deduplicated[key] for key in order][-MAX_HISTORY:]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--current", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--source-workflow", default="User Experience Empty State Recovery Trend")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    previous = _load_list(args.previous)
    current = json.loads(args.current.read_text(encoding="utf-8"))
    if not isinstance(current, dict):
        raise ValueError("current deve conter um objeto JSON")

    chain = build_chain(
        previous,
        current,
        run_id=args.run_id,
        head_sha=args.head_sha,
        source_workflow=args.source_workflow,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(chain, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"samples": len(chain), "latest_run_id": chain[-1]["source_run_id"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
