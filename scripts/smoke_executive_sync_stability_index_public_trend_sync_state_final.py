#!/usr/bin/env python3
"""Valida a publicação final do estado sincronizado no Ops Dashboard.

O resultado é informativo: nunca altera readiness, deploy ou decisão de produção.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

CARD_KEY = "executive_sync_stability_index_public_trend_sync_state"
CARD_ID = "executive-sync-stability-index-public-trend-sync-state"
MAX_SAMPLES = 90


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Contrato JSON inválido em {path}")
    return value


def _canonical(card: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": card.get("status"),
        "coverage_complete": bool(card.get("coverage_complete", False)),
        "synchronized": bool(card.get("synchronized", False)),
        "total_samples": int(card.get("total_samples", 0) or 0),
        "weighted_pass_rate_percent": float(card.get("weighted_pass_rate_percent", 0.0) or 0.0),
        "minimum_stable_sequence": int(card.get("minimum_stable_sequence", 0) or 0),
        "eligible_for_human_review": bool(card.get("eligible_for_human_review", False)),
        "mode": card.get("mode"),
        "production_blocker": card.get("production_blocker"),
        "human_approval_required": card.get("human_approval_required"),
    }


def _fingerprint(value: dict[str, Any]) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate(html_text: str, runtime: dict[str, Any], brief: dict[str, Any], environment: str) -> dict[str, Any]:
    runtime_card = runtime.get("cards", {}).get(CARD_KEY, {})
    brief_card = brief.get(CARD_KEY, {})
    runtime_contract = _canonical(runtime_card if isinstance(runtime_card, dict) else {})
    brief_contract = _canonical(brief_card if isinstance(brief_card, dict) else {})
    errors: list[str] = []

    if html_text.count(f'id="{CARD_ID}"') != 1:
        errors.append("public card must be present exactly once")
    if runtime_contract["mode"] != "report-only":
        errors.append("runtime mode must be report-only")
    if runtime_contract["production_blocker"] is not False:
        errors.append("runtime production_blocker must be false")
    if runtime_contract["human_approval_required"] is not True:
        errors.append("runtime human approval must be required")
    if brief_contract["mode"] != "report-only":
        errors.append("brief mode must be report-only")
    if brief_contract["production_blocker"] is not False:
        errors.append("brief production_blocker must be false")
    if brief_contract["human_approval_required"] is not True:
        errors.append("brief human approval must be required")

    comparable_fields = (
        "status", "coverage_complete", "synchronized", "total_samples",
        "weighted_pass_rate_percent", "minimum_stable_sequence",
        "eligible_for_human_review", "mode", "production_blocker",
        "human_approval_required",
    )
    for field in comparable_fields:
        if runtime_contract[field] != brief_contract[field]:
            errors.append(f"runtime/brief drift: {field}")

    synchronized = not errors
    status = "PUBLIC_FINAL_SYNC_OK" if synchronized else "PUBLIC_FINAL_SYNC_REVIEW"
    return {
        "environment": environment,
        "status": status,
        "synchronized": synchronized,
        "errors": errors,
        "fingerprint": _fingerprint(runtime_contract),
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
        "eligible_for_human_review": synchronized and runtime_contract["coverage_complete"] and runtime_contract["synchronized"],
    }


def append_history(history: dict[str, Any], sample: dict[str, Any]) -> dict[str, Any]:
    environment = sample["environment"]
    samples = [s for s in history.get("samples", []) if isinstance(s, dict) and s.get("environment") == environment]
    if not samples or samples[-1] != sample:
        samples.append(sample)
    samples = samples[-MAX_SAMPLES:]
    passed = sum(1 for item in samples if item.get("status") == "PUBLIC_FINAL_SYNC_OK")
    stable = 0
    for item in reversed(samples):
        if item.get("status") == "PUBLIC_FINAL_SYNC_OK":
            stable += 1
        else:
            break
    return {
        "samples": samples,
        "summary": {
            "environment": environment,
            "sample_count": len(samples),
            "pass_rate": round((passed / len(samples) * 100.0) if samples else 0.0, 2),
            "stable_sequence": stable,
            "mode": "report-only",
            "production_blocker": False,
            "human_approval_required": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", required=True, type=Path)
    parser.add_argument("--runtime-index", required=True, type=Path)
    parser.add_argument("--executive-brief", required=True, type=Path)
    parser.add_argument("--environment", required=True, choices=("dev", "stg", "prod"))
    parser.add_argument("--history", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    args = parser.parse_args()

    history = _load(args.history) if args.history.exists() else {}
    sample = validate(
        args.html.read_text(encoding="utf-8"),
        _load(args.runtime_index),
        _load(args.executive_brief),
        args.environment,
    )
    updated = append_history(history, sample)
    args.history.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.history.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.evidence.write_text(json.dumps(sample, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
