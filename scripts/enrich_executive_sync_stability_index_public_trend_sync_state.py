#!/usr/bin/env python3
"""Consolida o histórico sincronizado da tendência pública no Estado Único.

O sinal é estritamente informativo: não altera readiness, production_ready,
deploy ou decisões de promoção.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

ENVIRONMENTS = ("dev", "stg", "prod")
CARD_KEY = "executive_sync_stability_index_public_trend_sync_state"


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
    count = int(summary.get("sample_count", len(samples)) or 0)
    pass_rate = float(summary.get("pass_rate", 0.0) or 0.0)
    stable_sequence = int(summary.get("stable_sequence", 0) or 0)
    synchronized = bool(latest.get("synchronized", False))
    latest_status = str(latest.get("status", "UNKNOWN"))
    sufficient = (
        count >= 3
        and pass_rate == 100.0
        and stable_sequence >= 3
        and synchronized
        and latest_status == "PUBLIC_TREND_SYNC_OK"
    )
    return {
        "environment": environment,
        "sample_count": count,
        "pass_rate_percent": round(pass_rate, 2),
        "stable_sequence": stable_sequence,
        "synchronized": synchronized,
        "latest_status": latest_status,
        "evidence_sufficient": sufficient,
        "production_blocker": False,
    }


def build_state(histories: dict[str, dict[str, Any]]) -> dict[str, Any]:
    environments = {name: _summary(histories.get(name, {}), name) for name in ENVIRONMENTS}
    covered = [name for name, item in environments.items() if item["sample_count"] > 0]
    missing = [name for name in ENVIRONMENTS if name not in covered]
    total_samples = sum(item["sample_count"] for item in environments.values())
    weighted_pass = (
        sum(item["pass_rate_percent"] * item["sample_count"] for item in environments.values()) / total_samples
        if total_samples else 0.0
    )
    minimum_sequence = min((item["stable_sequence"] for item in environments.values()), default=0)
    coverage_complete = not missing
    synchronized = coverage_complete and all(item["synchronized"] for item in environments.values())
    eligible = coverage_complete and synchronized and all(item["evidence_sufficient"] for item in environments.values())

    if not coverage_complete:
        status = "insufficient-environment-coverage"
    elif any(item["latest_status"] != "PUBLIC_TREND_SYNC_OK" for item in environments.values()):
        status = "attention"
    elif not synchronized:
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
        "status": state["status"],
        "coverage_complete": state["coverage_complete"],
        "synchronized": state["synchronized"],
        "total_samples": state["total_samples"],
        "weighted_pass_rate_percent": state["weighted_pass_rate_percent"],
        "minimum_stable_sequence": state["minimum_stable_sequence"],
        "eligible_for_human_review": state["eligible_for_human_review"],
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }
    return runtime, brief


def main() -> int:
    parser = argparse.ArgumentParser()
    for environment in ENVIRONMENTS:
        parser.add_argument(f"--{environment}-history", required=True, type=Path)
    parser.add_argument("--runtime-index", required=True, type=Path)
    parser.add_argument("--executive-brief", required=True, type=Path)
    parser.add_argument("--output-runtime-index", type=Path)
    parser.add_argument("--output-executive-brief", type=Path)
    args = parser.parse_args()
    histories = {name: _load(getattr(args, f"{name}_history")) for name in ENVIRONMENTS}
    runtime, brief = enrich(_load(args.runtime_index), _load(args.executive_brief), histories)
    _write(args.output_runtime_index or args.runtime_index, runtime)
    _write(args.output_executive_brief or args.executive_brief, brief)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
