#!/usr/bin/env python3
"""Consolida o histórico final DEV/STG/PROD no Estado Único e Executive Brief.

O sinal é estritamente informativo e nunca altera readiness, production_ready,
deploy ou decisões de promoção.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

ENVIRONMENTS = ("dev", "stg", "prod")
CARD_KEY = "executive_final_sync_history_state"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Contrato JSON inválido em {path}")
    return value


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _summary(history: dict[str, Any], environment: str) -> dict[str, Any]:
    samples = [s for s in history.get("samples", []) if isinstance(s, dict) and s.get("environment") == environment]
    summary = history.get("summary", {}) if isinstance(history.get("summary"), dict) else {}
    latest = samples[-1] if samples else {}
    sample_count = int(summary.get("sample_count", len(samples)) or 0)
    pass_rate = float(summary.get("pass_rate_percent", summary.get("pass_rate", 0.0)) or 0.0)
    stable_sequence = int(summary.get("stable_sequence", 0) or 0)
    latest_status = str(latest.get("status", "UNKNOWN"))
    synchronized = bool(latest.get("synchronized", False))
    fingerprint = str(latest.get("fingerprint", ""))
    evidence_sufficient = (
        sample_count >= 3
        and pass_rate == 100.0
        and stable_sequence >= 3
        and latest_status == "PUBLIC_FINAL_SYNC_OK"
        and synchronized
        and bool(fingerprint)
    )
    return {
        "environment": environment,
        "sample_count": sample_count,
        "pass_rate_percent": round(pass_rate, 2),
        "stable_sequence": stable_sequence,
        "latest_status": latest_status,
        "synchronized": synchronized,
        "fingerprint": fingerprint,
        "evidence_sufficient": evidence_sufficient,
        "production_blocker": False,
    }


def build_state(histories: dict[str, dict[str, Any]]) -> dict[str, Any]:
    environments = {env: _summary(histories.get(env, {}), env) for env in ENVIRONMENTS}
    covered = [env for env, item in environments.items() if item["sample_count"] > 0]
    missing = [env for env in ENVIRONMENTS if env not in covered]
    fingerprints = {item["fingerprint"] for item in environments.values() if item["fingerprint"]}
    coverage_complete = not missing
    synchronized = coverage_complete and all(item["synchronized"] for item in environments.values())
    no_drift = coverage_complete and len(fingerprints) == 1
    eligible = coverage_complete and synchronized and no_drift and all(item["evidence_sufficient"] for item in environments.values())
    total_samples = sum(item["sample_count"] for item in environments.values())
    weighted_pass = (
        sum(item["pass_rate_percent"] * item["sample_count"] for item in environments.values()) / total_samples
        if total_samples else 0.0
    )
    minimum_sequence = min((item["stable_sequence"] for item in environments.values()), default=0)

    if not coverage_complete:
        status = "insufficient-environment-coverage"
    elif any(item["latest_status"] != "PUBLIC_FINAL_SYNC_OK" for item in environments.values()):
        status = "attention"
    elif not synchronized or not no_drift:
        status = "drift-detected"
    elif eligible:
        status = "eligible-for-human-review"
    else:
        status = "collecting-evidence"

    return {
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
        "decision_scope": "human-review-only",
        "status": status,
        "coverage_complete": coverage_complete,
        "synchronized": synchronized,
        "no_drift": no_drift,
        "covered_environments": covered,
        "missing_environments": missing,
        "total_samples": total_samples,
        "weighted_pass_rate_percent": round(weighted_pass, 2),
        "minimum_stable_sequence": minimum_sequence,
        "eligible_for_human_review": eligible,
        "environments": environments,
    }


def enrich(runtime_index: dict[str, Any], executive_brief: dict[str, Any], histories: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    runtime = copy.deepcopy(runtime_index)
    brief = copy.deepcopy(executive_brief)
    state = build_state(histories)
    runtime.setdefault("cards", {})[CARD_KEY] = state
    brief[CARD_KEY] = {
        key: state[key]
        for key in (
            "status", "coverage_complete", "synchronized", "no_drift", "total_samples",
            "weighted_pass_rate_percent", "minimum_stable_sequence", "eligible_for_human_review",
            "mode", "production_blocker", "human_approval_required",
        )
    }
    return runtime, brief


def main() -> int:
    parser = argparse.ArgumentParser()
    for env in ENVIRONMENTS:
        parser.add_argument(f"--{env}-history", required=True, type=Path)
    parser.add_argument("--runtime-index", required=True, type=Path)
    parser.add_argument("--executive-brief", required=True, type=Path)
    parser.add_argument("--output-runtime-index", type=Path)
    parser.add_argument("--output-executive-brief", type=Path)
    args = parser.parse_args()
    histories = {env: _load(getattr(args, f"{env}_history")) for env in ENVIRONMENTS}
    runtime, brief = enrich(_load(args.runtime_index), _load(args.executive_brief), histories)
    _write(args.output_runtime_index or args.runtime_index, runtime)
    _write(args.output_executive_brief or args.executive_brief, brief)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
