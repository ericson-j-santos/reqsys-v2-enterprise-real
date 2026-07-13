#!/usr/bin/env python3
"""Smoke sincronizado do card de tendência pública final.

Fluxo exclusivamente informativo: não altera readiness nem produção.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CARD_ID = "executive-final-sync-history-public-smoke-trend"
CARD_KEY = "executive_final_sync_history_public_smoke_trend"
SAFE_GUARDRAILS = {
    "mode": "report-only",
    "production_blocker": False,
    "human_approval_required": True,
}


def canonical_payload(card: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": card.get("status"),
        "environment_coverage": card.get("environment_coverage"),
        "sample_count": card.get("sample_count"),
        "weighted_pass_rate": card.get("weighted_pass_rate"),
        "minimum_stable_sequence": card.get("minimum_stable_sequence"),
        "synchronized": card.get("synchronized"),
        "common_fingerprint": card.get("common_fingerprint"),
        "guardrails": SAFE_GUARDRAILS,
    }


def fingerprint(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def evaluate(html: str, runtime: dict[str, Any], brief: dict[str, Any], environment: str) -> dict[str, Any]:
    runtime_card = runtime.get("cards", {}).get(CARD_KEY, {})
    brief_card = brief.get("indicators", {}).get(CARD_KEY, {})
    runtime_payload = canonical_payload(runtime_card)
    brief_payload = canonical_payload(brief_card)
    issues: list[str] = []

    if html.count(f'id="{CARD_ID}"') != 1:
        issues.append("public_card_presence")
    if runtime_payload != brief_payload:
        issues.append("runtime_brief_drift")
    if runtime_card.get("mode") not in (None, "report-only"):
        issues.append("unsafe_mode")
    if runtime_card.get("production_blocker") not in (None, False):
        issues.append("unsafe_production_blocker")
    if runtime_card.get("human_approval_required") not in (None, True):
        issues.append("missing_human_approval")

    status = "PUBLIC_FINAL_TREND_SYNC_OK" if not issues else "PUBLIC_FINAL_TREND_SYNC_REVIEW"
    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "environment": environment,
        "status": status,
        "issues": issues,
        "fingerprint": fingerprint(runtime_payload),
        "guardrails": SAFE_GUARDRAILS,
    }


def update_history(history: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    samples = list(history.get("samples", []))
    identity = (evidence["environment"], evidence["fingerprint"], evidence["status"])
    if not any((s.get("environment"), s.get("fingerprint"), s.get("status")) == identity for s in samples):
        samples.append(evidence)
    return {"schema_version": "1.0.0", "samples": samples[-90:]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard", required=True)
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--brief", required=True)
    parser.add_argument("--environment", choices=("dev", "stg", "prod"), required=True)
    parser.add_argument("--history")
    parser.add_argument("--evidence-out", required=True)
    parser.add_argument("--history-out", required=True)
    args = parser.parse_args()

    html = Path(args.dashboard).read_text(encoding="utf-8")
    runtime = json.loads(Path(args.runtime).read_text(encoding="utf-8"))
    brief = json.loads(Path(args.brief).read_text(encoding="utf-8"))
    history = json.loads(Path(args.history).read_text(encoding="utf-8")) if args.history and Path(args.history).exists() else {}
    evidence = evaluate(html, runtime, brief, args.environment)
    Path(args.evidence_out).write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    Path(args.history_out).write_text(json.dumps(update_history(history, evidence), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
