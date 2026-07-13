#!/usr/bin/env python3
"""Consolida histórico sincronizado DEV/STG/PROD no Estado Único e Executive Brief.

O resultado é sempre informativo: não altera readiness, production_ready ou deploy.
"""
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

ENVIRONMENTS = ("DEV", "STG", "PROD")
MIN_SAMPLES = 3
MIN_STABLE_STREAK = 3


def _samples(history: dict[str, Any]) -> list[dict[str, Any]]:
    value = history.get("samples", [])
    return value if isinstance(value, list) else []


def consolidate(histories: dict[str, dict[str, Any]]) -> dict[str, Any]:
    coverage = [env for env in ENVIRONMENTS if _samples(histories.get(env, {}))]
    metrics: dict[str, Any] = {}
    fingerprints: set[str] = set()
    eligible = len(coverage) == len(ENVIRONMENTS)

    for env in ENVIRONMENTS:
        samples = _samples(histories.get(env, {}))
        ok_count = sum(1 for item in samples if item.get("status") == "PUBLIC_FINAL_TREND_SYNC_OK")
        pass_rate = round(ok_count / len(samples) * 100, 2) if samples else 0.0
        stable_streak = int(histories.get(env, {}).get("stable_streak", 0) or 0)
        fingerprint = str(histories.get(env, {}).get("fingerprint", "") or "")
        if fingerprint:
            fingerprints.add(fingerprint)
        metrics[env] = {
            "samples": len(samples),
            "pass_rate": pass_rate,
            "stable_streak": stable_streak,
            "fingerprint": fingerprint,
        }
        eligible = eligible and len(samples) >= MIN_SAMPLES and pass_rate == 100.0 and stable_streak >= MIN_STABLE_STREAK

    synchronized = len(fingerprints) == 1 and len(fingerprints) > 0
    eligible = eligible and synchronized

    if len(coverage) < len(ENVIRONMENTS):
        status = "insufficient-environment-coverage"
    elif not synchronized:
        status = "drift-detected"
    elif any(metrics[env]["pass_rate"] < 100.0 for env in ENVIRONMENTS):
        status = "attention"
    elif not eligible:
        status = "collecting-evidence"
    else:
        status = "eligible-for-human-review"

    return {
        "status": status,
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
        "coverage": coverage,
        "synchronized": synchronized,
        "common_fingerprint": next(iter(fingerprints)) if synchronized else None,
        "environments": metrics,
        "eligible_for_human_review": eligible,
    }


def enrich(state: dict[str, Any], brief: dict[str, Any], result: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    state_out = deepcopy(state)
    brief_out = deepcopy(brief)
    state_out.setdefault("cards", {})["executive_final_trend_sync_history_state"] = result
    brief_out.setdefault("indicators", {})["executive_final_trend_sync_history_state"] = result
    return state_out, brief_out


def _load(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write(path: str, data: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", required=True)
    parser.add_argument("--stg", required=True)
    parser.add_argument("--prod", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--brief", required=True)
    parser.add_argument("--out-state", required=True)
    parser.add_argument("--out-brief", required=True)
    parser.add_argument("--out-evidence", required=True)
    args = parser.parse_args()

    histories = {"DEV": _load(args.dev), "STG": _load(args.stg), "PROD": _load(args.prod)}
    result = consolidate(histories)
    state_out, brief_out = enrich(_load(args.state), _load(args.brief), result)
    _write(args.out_state, state_out)
    _write(args.out_brief, brief_out)
    _write(args.out_evidence, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
