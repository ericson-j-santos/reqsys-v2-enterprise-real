#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCORE = {"green": 100, "yellow": 70, "unknown": 40, "red": 0}


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def norm(value: Any, default: str = "unknown") -> str:
    raw = str(value if value is not None else default).strip().lower()
    aliases = {
        "passed": "green",
        "success": "green",
        "healthy": "green",
        "ready": "green",
        "true": "green",
        "warning": "yellow",
        "review": "yellow",
        "pending": "yellow",
        "blocked": "red",
        "failed": "red",
        "critical": "red",
        "false": "red",
    }
    return aliases.get(raw, raw if raw in SCORE else default)


def build(runtime: dict[str, Any], readiness: dict[str, Any], security: dict[str, Any], merge: dict[str, Any], history: dict[str, Any], correlation_id: str) -> dict[str, Any]:
    runtime_summary = runtime.get("summary") or {}
    ready = readiness.get("executive_readiness") or {}
    security_overall = security.get("overall") or {}
    severity = ((security.get("totals") or {}).get("severity") or {})
    history_summary = history.get("summary") or {}

    states = {
        "runtime": norm(runtime_summary.get("status") or runtime_summary.get("production_ready")),
        "executive_readiness": "red" if ready.get("blockers") else ("green" if ready.get("ready_for_production") is True else norm(ready.get("overall_state") or ready.get("decision"), "yellow")),
        "security": "red" if security_overall.get("production_blocked") or int(severity.get("critical") or 0) > 0 else ("yellow" if int(severity.get("high") or 0) > 0 else norm(security_overall.get("state") or security_overall.get("decision"), "green" if security else "unknown")),
        "merge_readiness": "red" if merge.get("mergeable") is False or merge.get("blocked") is True else ("green" if merge.get("mergeable") is True or merge.get("ready") is True else norm(merge.get("state") or merge.get("status"), "unknown")),
        "workflow_efficiency": "yellow" if history_summary.get("latest_decision") == "BLOCKED" else ("green" if history_summary.get("latest_decision") == "HOMOLOGATED" else norm(history_summary.get("latest_status"), "unknown")),
    }

    if "red" in states.values():
        decision = "HOLD"
        recommendation = "Revisar os domínios em vermelho antes da promoção."
    elif any(state in {"yellow", "unknown"} for state in states.values()):
        decision = "REVIEW"
        recommendation = "Executar revisão humana dos domínios sem evidência suficiente."
    else:
        decision = "READY"
        recommendation = "Promoção recomendada, sujeita aos gates e aprovação humana existentes."

    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id,
        "mode": "report-only",
        "decision": decision,
        "confidence_percent": round(sum(SCORE[state] for state in states.values()) / len(states), 2),
        "production_blocker": False,
        "human_approval_required": True,
        "inputs": states,
        "risk_domains": [name for name, state in states.items() if state != "green"],
        "recommendation": recommendation,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-index", type=Path, required=True)
    parser.add_argument("--executive-readiness", type=Path, required=True)
    parser.add_argument("--security-summary", type=Path, required=True)
    parser.add_argument("--merge-readiness", type=Path, required=True)
    parser.add_argument("--workflow-efficiency-history", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--correlation-id", default="local")
    args = parser.parse_args()
    payload = build(load(args.runtime_index), load(args.executive_readiness), load(args.security_summary), load(args.merge_readiness), load(args.workflow_efficiency_history), args.correlation_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
