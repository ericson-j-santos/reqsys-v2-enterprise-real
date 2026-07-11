#!/usr/bin/env python3
"""Acumula histórico temporal do smoke público do Advisor por ambiente."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def build(previous: dict[str, Any], evidence: dict[str, Any], max_samples: int = 90) -> dict[str, Any]:
    environment = str(evidence.get("environment") or "unknown").lower()
    environments = dict(previous.get("environments") or {})
    current_env = dict(environments.get(environment) or {})
    entries = list(current_env.get("entries") or [])

    entry = {
        "generated_at": evidence.get("generated_at"),
        "status": evidence.get("status"),
        "decision": evidence.get("decision"),
        "public_url": evidence.get("public_url"),
        "trend": (evidence.get("advisor_trend") or {}).get("trend"),
        "sample_count": (evidence.get("advisor_trend") or {}).get("sample_count"),
        "eligible_for_gate_review": bool(
            (evidence.get("advisor_trend") or {}).get("eligible_for_gate_review")
        ),
        "error_count": len(evidence.get("errors") or []),
    }
    dedupe_key = (entry["generated_at"], entry["decision"], entry["public_url"])
    entries = [
        item for item in entries
        if (item.get("generated_at"), item.get("decision"), item.get("public_url")) != dedupe_key
    ]
    entries.append(entry)
    entries = entries[-max_samples:]

    total = len(entries)
    passed = sum(1 for item in entries if item.get("status") == "passed")
    stable_streak = 0
    for item in reversed(entries):
        if item.get("status") == "passed":
            stable_streak += 1
        else:
            break

    environments[environment] = {
        "summary": {
            "sample_count": total,
            "pass_rate_percent": round(passed * 100 / total, 2) if total else 0,
            "stable_streak": stable_streak,
            "latest_status": entry["status"],
            "latest_decision": entry["decision"],
            "eligible_for_human_review": bool(entry["eligible_for_gate_review"]),
            "production_blocker": False,
        },
        "entries": entries,
    }

    global_samples = sum(int((value.get("summary") or {}).get("sample_count") or 0) for value in environments.values())
    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
        "summary": {
            "environment_count": len(environments),
            "sample_count": global_samples,
            "production_blocker": False,
        },
        "environments": environments,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Histórico de smoke público do Advisor")
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--previous-history", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-samples", type=int, default=90)
    args = parser.parse_args()

    evidence = load(args.evidence)
    if not evidence:
        raise SystemExit("evidência de smoke ausente ou vazia")
    if evidence.get("production_blocker") is not False:
        raise SystemExit("evidência inválida: production_blocker deve ser false")

    payload = build(load(args.previous_history), evidence, args.max_samples)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    environment = evidence.get("environment")
    print(json.dumps(payload["environments"][environment]["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
