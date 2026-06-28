#!/usr/bin/env python3
"""Build a dashboard-ready card for Autonomous Delivery Cycle.

Offline/static builder: no GitHub API calls at runtime.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


def load_json(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    return json.loads(file_path.read_text(encoding="utf-8"))


def _status_to_risk(status: str) -> str:
    normalized = (status or "unknown").lower()
    if normalized in {"passed", "success", "green", "empty", "empty_seed", "seed"}:
        return "low"
    if normalized in {"failed", "failure", "post_merge_attention_required", "blocked"}:
        return "high"
    return "medium"


def build_card(latest: dict[str, Any] | None = None, queue: dict[str, Any] | None = None) -> dict[str, Any]:
    latest = latest or {}
    queue = queue or {}
    decisions = latest.get("decisions") or []
    next_increments = queue.get("queue") or latest.get("next_increments") or []
    merged_count = int(latest.get("merged_count") or 0)
    eligible_count = int(latest.get("eligible_count") or 0)
    candidate_count = int(latest.get("candidate_count") or 0)
    blockers = [blocker for decision in decisions for blocker in decision.get("blockers", [])]
    post_merge_attention = any(
        (decision.get("post_merge") or {}).get("status") == "post_merge_attention_required"
        for decision in decisions
    )
    queue_status = str(queue.get("status") or "empty_seed")
    status = "post_merge_attention_required" if post_merge_attention else "passed" if latest else "seed"
    risk = "high" if blockers or post_merge_attention else _status_to_risk(queue_status)

    return {
        "schema_version": "1.0.0",
        "card": "autonomous_delivery_cycle",
        "generated_at_epoch": int(time.time()),
        "status": status,
        "risk": risk,
        "summary": "Ciclo governado de auto-merge condicionado a CI verde, labels explícitas e fila report-only.",
        "metrics": {
            "candidate_count": candidate_count,
            "eligible_count": eligible_count,
            "merged_count": merged_count,
            "blocker_count": len(blockers),
            "next_increment_queue_count": len(next_increments),
        },
        "latest": {
            "mode": latest.get("mode", "seed"),
            "required_label": latest.get("required_label", "cycle:auto-merge-approved"),
            "max_prs": latest.get("max_prs", 1),
        },
        "queue": {
            "status": queue_status,
            "items": next_increments[:10],
        },
        "links": {
            "latest_contract": "docs/ops-dashboard/data/autonomous-delivery-cycle-latest.json",
            "next_increments": "docs/ops-dashboard/data/autonomous-delivery-cycle-next-increments.json",
            "policy": "docs/ops-dashboard/data/autonomous-delivery-cycle-policy.json",
            "workflow": ".github/workflows/autonomous-delivery-cycle.yml",
            "runbook": "docs/runbooks/autonomous-delivery-cycle.md",
        },
        "guardrails": [
            "offline_static_generation",
            "no_runtime_github_api_call",
            "queue_is_report_only",
            "safe_fallback_when_source_artifact_missing",
            "post_merge_attention_blocks_next_increment",
        ],
        "design": {
            "trilha_c_reference": "docs/adr/ADR-038-trilha-c-ux-operacional.md",
            "spa_surface": "/monitoramento-operacional?secao=autonomous-cycle",
            "figma_github_route": "/figma-github",
            "ops_dashboard_static": "https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/blob/main/docs/ops-dashboard/index.html#autonomous-delivery-cycle",
            "figma_note": "Superficie Trilha C na SPA; arquivo Figma via /figma-github quando FIGMA_DEFAULT_FILE_KEY estiver configurado.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Autonomous Delivery Cycle dashboard card")
    parser.add_argument("--latest", default="docs/ops-dashboard/data/autonomous-delivery-cycle-latest.json")
    parser.add_argument("--queue", default="docs/ops-dashboard/data/autonomous-delivery-cycle-next-increments.json")
    parser.add_argument("--output", default="docs/ops-dashboard/data/autonomous-delivery-cycle-dashboard-card.json")
    args = parser.parse_args()

    payload = build_card(load_json(args.latest), load_json(args.queue))
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
