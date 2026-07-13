#!/usr/bin/env python3
"""Valida disponibilidade e sincronização pública do histórico final executivo.

O resultado é apenas informativo e nunca altera readiness, deploy ou produção.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

CARD_KEY = "executive_final_sync_history_state"
CARD_ID = "executive-final-sync-history-state"
STATUS_OK = "PUBLIC_FINAL_HISTORY_SMOKE_OK"
STATUS_REVIEW = "PUBLIC_FINAL_HISTORY_SMOKE_REVIEW"


def _canonical(card: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": str(card.get("status", "unknown")),
        "coverage_complete": bool(card.get("coverage_complete", False)),
        "synchronized": bool(card.get("synchronized", False)),
        "total_samples": int(card.get("total_samples", 0) or 0),
        "weighted_pass_rate_percent": float(card.get("weighted_pass_rate_percent", 0.0) or 0.0),
        "minimum_stable_sequence": int(card.get("minimum_stable_sequence", 0) or 0),
        "common_fingerprint": str(card.get("common_fingerprint", "")),
        "eligible_for_human_review": bool(card.get("eligible_for_human_review", False)),
        "mode": str(card.get("mode", "")),
        "production_blocker": card.get("production_blocker"),
        "human_approval_required": card.get("human_approval_required"),
    }


def _fingerprint(value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def evaluate(html_text: str, runtime_index: dict[str, Any], executive_brief: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    runtime_card = runtime_index.get("cards", {}).get(CARD_KEY)
    brief_card = executive_brief.get(CARD_KEY)
    if not isinstance(runtime_card, dict):
        errors.append("missing runtime card")
        runtime_card = {}
    if not isinstance(brief_card, dict):
        errors.append("missing executive brief card")
        brief_card = {}

    runtime_contract = _canonical(runtime_card)
    brief_contract = _canonical(brief_card)
    if html_text.count(f'id="{CARD_ID}"') != 1:
        errors.append("public card must be present exactly once")
    if runtime_contract != brief_contract:
        errors.append("runtime and executive brief contracts diverge")
    if runtime_contract.get("mode") != "report-only":
        errors.append("mode must be report-only")
    if runtime_contract.get("production_blocker") is not False:
        errors.append("production_blocker must be false")
    if runtime_contract.get("human_approval_required") is not True:
        errors.append("human approval must be required")

    return {
        "status": STATUS_OK if not errors else STATUS_REVIEW,
        "available": not any("missing" in item or "present" in item for item in errors),
        "synchronized": runtime_contract == brief_contract and not errors,
        "fingerprint": _fingerprint(runtime_contract),
        "errors": errors,
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }


def append_history(history: dict[str, Any], environment: str, evidence: dict[str, Any]) -> dict[str, Any]:
    samples = [item for item in history.get("samples", []) if isinstance(item, dict)]
    sample = {"environment": environment, **evidence}
    identity = (environment, evidence["status"], evidence["fingerprint"])
    if not samples or (samples[-1].get("environment"), samples[-1].get("status"), samples[-1].get("fingerprint")) != identity:
        samples.append(sample)
    samples = samples[-90:]
    passed = sum(1 for item in samples if item.get("status") == STATUS_OK)
    return {
        "samples": samples,
        "summary": {
            "environment": environment,
            "sample_count": len(samples),
            "pass_rate": round((passed / len(samples) * 100.0) if samples else 0.0, 2),
            "stable_sequence": _stable_sequence(samples),
        },
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }


def _stable_sequence(samples: list[dict[str, Any]]) -> int:
    count = 0
    for item in reversed(samples):
        if item.get("status") != STATUS_OK:
            break
        count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", required=True, type=Path)
    parser.add_argument("--runtime-index", required=True, type=Path)
    parser.add_argument("--executive-brief", required=True, type=Path)
    parser.add_argument("--environment", required=True, choices=("dev", "stg", "prod"))
    parser.add_argument("--history", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    args = parser.parse_args()

    runtime = json.loads(args.runtime_index.read_text(encoding="utf-8"))
    brief = json.loads(args.executive_brief.read_text(encoding="utf-8"))
    evidence = evaluate(args.html.read_text(encoding="utf-8"), runtime, brief)
    history = json.loads(args.history.read_text(encoding="utf-8")) if args.history.exists() else {}
    updated_history = append_history(history, args.environment, evidence)
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.history.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.history.write_text(json.dumps(updated_history, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
