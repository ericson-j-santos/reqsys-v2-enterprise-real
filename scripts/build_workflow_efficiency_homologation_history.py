#!/usr/bin/env python3
"""Constrói histórico e tendência da homologação Workflow Efficiency."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def normalize_entry(evidence: dict[str, Any]) -> dict[str, Any]:
    details = evidence.get("workflow_efficiency") or {}
    status = str(evidence.get("status") or "unknown").lower()
    decision = str(evidence.get("decision") or "UNKNOWN").upper()
    return {
        "correlation_id": evidence.get("correlation_id"),
        "generated_at": evidence.get("generated_at"),
        "status": status,
        "decision": decision,
        "homologated": status == "passed" and decision == "HOMOLOGATED",
        "score_percent": details.get("score_percent"),
        "mode": details.get("mode") or "report-only",
        "error_count": len(evidence.get("errors") or []),
    }


def build_history(previous: dict[str, Any], evidence: dict[str, Any], max_samples: int = 50) -> dict[str, Any]:
    entries = list(previous.get("entries") or [])
    current = normalize_entry(evidence)
    correlation_id = current.get("correlation_id")
    entries = [entry for entry in entries if entry.get("correlation_id") != correlation_id]
    entries.append(current)
    entries = entries[-max_samples:]

    total = len(entries)
    homologated_count = sum(1 for entry in entries if entry.get("homologated"))
    pass_rate = round((homologated_count / total) * 100, 2) if total else 0.0

    stable_streak = 0
    for entry in reversed(entries):
        if entry.get("homologated"):
            stable_streak += 1
        else:
            break

    scores = [float(entry["score_percent"]) for entry in entries if entry.get("score_percent") is not None]
    trend_delta = round(scores[-1] - scores[-2], 2) if len(scores) >= 2 else 0.0
    trend = "up" if trend_delta > 0 else "down" if trend_delta < 0 else "stable"

    eligible_for_blocking_review = total >= 30 and pass_rate >= 98.0 and stable_streak >= 20

    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "report-only",
        "summary": {
            "sample_count": total,
            "homologated_count": homologated_count,
            "pass_rate_percent": pass_rate,
            "stable_streak": stable_streak,
            "latest_status": current["status"],
            "latest_decision": current["decision"],
            "latest_score_percent": current.get("score_percent"),
            "trend": trend,
            "trend_delta_points": trend_delta,
            "eligible_for_blocking_review": eligible_for_blocking_review,
            "production_blocker": False,
        },
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Constrói histórico da homologação Workflow Efficiency")
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--previous-history", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-samples", type=int, default=50)
    args = parser.parse_args()

    evidence = load_json(args.evidence)
    if not evidence:
        raise SystemExit("evidência ausente ou inválida")
    previous = load_json(args.previous_history) if args.previous_history else {}
    history = build_history(previous, evidence, args.max_samples)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(history["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
