#!/usr/bin/env python3
"""Runtime Merge Queue Gate.

Gera uma decisao JSON deterministica para elegibilidade de merge queue
sensivel a CI, smoke runtime, incidentes e contrato publico.

Uso:
  python scripts/runtime_merge_queue_gate.py \
    --lane runtime-governance \
    --ci green \
    --runtime-smoke green \
    --incidents none-critical \
    --contracts green \
    --json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GREEN_VALUES = {"green", "success", "ok", "passed"}
PENDING_VALUES = {"pending", "queued", "in_progress", "waiting"}
CRITICAL_INCIDENT_VALUES = {"critical", "critical-open", "open-critical", "red"}


def normalize(value: str) -> str:
    return (value or "unknown").strip().lower()


def evaluate_gate(
    *,
    lane: str,
    ci: str,
    runtime_smoke: str,
    incidents: str,
    contracts: str,
    mergeable: str,
) -> dict[str, Any]:
    ci_status = normalize(ci)
    smoke_status = normalize(runtime_smoke)
    incidents_status = normalize(incidents)
    contracts_status = normalize(contracts)
    mergeable_status = normalize(mergeable)

    blocking_reasons: list[str] = []
    state = "eligible"

    if ci_status in PENDING_VALUES:
        blocking_reasons.append("ci_pending")
        state = "waiting_ci"
    elif ci_status not in GREEN_VALUES:
        blocking_reasons.append("ci_not_green")
        state = "blocked_by_ci"

    if smoke_status in PENDING_VALUES:
        blocking_reasons.append("runtime_smoke_pending")
        state = "waiting_runtime_smoke"
    elif smoke_status not in GREEN_VALUES:
        blocking_reasons.append("runtime_smoke_not_green")
        state = "blocked_by_runtime_smoke"

    if incidents_status in CRITICAL_INCIDENT_VALUES:
        blocking_reasons.append("critical_incident_open")
        state = "paused_by_incident"

    if contracts_status not in GREEN_VALUES:
        blocking_reasons.append("contracts_not_green")
        state = "blocked_by_contract"

    if mergeable_status not in {"true", "yes", "mergeable", "clean"}:
        blocking_reasons.append("not_mergeable")
        if state == "eligible":
            state = "requires_rebase"

    eligible = not blocking_reasons
    return {
        "eligible": eligible,
        "state": state if not eligible else "eligible",
        "lane": lane,
        "blocking_reasons": blocking_reasons,
        "evidence": {
            "ci": ci_status,
            "runtime_smoke": smoke_status,
            "incidents": incidents_status,
            "contracts": contracts_status,
            "mergeable": mergeable_status,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": "1.0.0",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Avalia elegibilidade de merge queue sensivel a runtime.")
    parser.add_argument("--lane", default="runtime-governance")
    parser.add_argument("--ci", default="pending")
    parser.add_argument("--runtime-smoke", default="pending")
    parser.add_argument("--incidents", default="none-critical")
    parser.add_argument("--contracts", default="green")
    parser.add_argument("--mergeable", default="true")
    parser.add_argument("--output", default="artifacts/runtime-governance/runtime-merge-queue-gate.json")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = evaluate_gate(
        lane=args.lane,
        ci=args.ci,
        runtime_smoke=args.runtime_smoke,
        incidents=args.incidents,
        contracts=args.contracts,
        mergeable=args.mergeable,
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"state={payload['state']} eligible={payload['eligible']}")

    return 0 if payload["eligible"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
