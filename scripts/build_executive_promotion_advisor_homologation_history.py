#!/usr/bin/env python3
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


def build(previous: dict[str, Any], evidence: dict[str, Any], max_samples: int = 50) -> dict[str, Any]:
    entries = list(previous.get("entries") or [])
    current = {
        "generated_at": evidence.get("generated_at"),
        "decision": evidence.get("decision"),
        "status": evidence.get("status"),
        "artifact_status": (evidence.get("artifact") or {}).get("status"),
        "public_status": (evidence.get("public_url") or {}).get("status"),
        "public_observed": bool((evidence.get("public_url") or {}).get("observed")),
        "error_count": len(evidence.get("errors") or []),
    }
    dedupe_key = (current["generated_at"], current["decision"])
    entries = [entry for entry in entries if (entry.get("generated_at"), entry.get("decision")) != dedupe_key]
    entries.append(current)
    entries = entries[-max_samples:]

    total = len(entries)
    artifact_passed = sum(1 for entry in entries if entry.get("artifact_status") == "passed")
    public_passed = sum(1 for entry in entries if entry.get("public_status") == "passed")
    full_homologated = sum(1 for entry in entries if entry.get("decision") == "HOMOLOGATED")

    stable_streak = 0
    for entry in reversed(entries):
        if entry.get("decision") == "HOMOLOGATED":
            stable_streak += 1
        else:
            break

    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "report-only",
        "summary": {
            "sample_count": total,
            "artifact_pass_rate_percent": round(artifact_passed * 100 / total, 2) if total else 0,
            "public_pass_rate_percent": round(public_passed * 100 / total, 2) if total else 0,
            "full_homologation_rate_percent": round(full_homologated * 100 / total, 2) if total else 0,
            "stable_streak": stable_streak,
            "latest_decision": current["decision"],
            "eligible_for_gate_review": total >= 30 and full_homologated * 100 / total >= 98 and stable_streak >= 20,
            "production_blocker": False,
        },
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--previous-history", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-samples", type=int, default=50)
    args = parser.parse_args()
    payload = build(load(args.previous_history), load(args.evidence), args.max_samples)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
