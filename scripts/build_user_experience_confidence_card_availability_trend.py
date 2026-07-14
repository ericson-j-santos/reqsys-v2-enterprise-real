#!/usr/bin/env python3
"""Consolida a tendência de disponibilidade do card de confiança UX.

Entrada: JSON com lista `samples`. Cada amostra deve conter `available`, `synced`,
`fingerprint`, `drift_detected` e opcionalmente `timestamp`.
Saída: relatório report-only e enriquecimento opcional do Estado Único/Executive Brief.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

CARD_KEY = "user_experience_sync_confidence_availability"


def _load(path: str | None, default: Any) -> Any:
    if not path:
        return copy.deepcopy(default)
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else copy.deepcopy(default)


def _dump(path: str | None, data: Any) -> None:
    if path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build(samples: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(samples)
    healthy = [
        bool(s.get("available"))
        and bool(s.get("synced"))
        and not bool(s.get("drift_detected"))
        for s in samples
    ]
    success_count = sum(healthy)
    success_rate = round((success_count / total) * 100, 2) if total else 0.0

    stable_sequence = 0
    for ok in reversed(healthy):
        if not ok:
            break
        stable_sequence += 1

    recent = samples[-3:]
    recurring_drift = bool(recent) and sum(bool(s.get("drift_detected")) for s in recent) >= 2
    fingerprints = {str(s.get("fingerprint")) for s in samples if s.get("fingerprint")}
    common_fingerprint = next(iter(fingerprints)) if len(fingerprints) == 1 else None

    eligible = (
        total >= 3
        and success_rate == 100.0
        and stable_sequence >= 3
        and not recurring_drift
        and common_fingerprint is not None
    )
    score = max(0, min(100, round(success_rate - (25 if recurring_drift else 0))))
    level = "HIGH" if score >= 95 else "MEDIUM" if score >= 80 else "LOW"

    return {
        "status": "UX_CONFIDENCE_CARD_AVAILABILITY_STABLE" if eligible else "UX_CONFIDENCE_CARD_AVAILABILITY_REVIEW",
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
        "sample_count": total,
        "success_count": success_count,
        "availability_rate": success_rate,
        "stable_sequence": stable_sequence,
        "recurring_drift": recurring_drift,
        "common_fingerprint": common_fingerprint,
        "confidence_score": score,
        "confidence_level": level,
        "human_review_eligible": eligible,
    }


def consolidate(history: dict[str, Any], state: dict[str, Any], brief: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    report = build(list(history.get("samples") or []))
    state_out = copy.deepcopy(state)
    brief_out = copy.deepcopy(brief)
    state_out.setdefault("cards", {})[CARD_KEY] = report
    brief_out.setdefault("indicators", {})[CARD_KEY] = report
    return report, state_out, brief_out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", required=True)
    parser.add_argument("--state-input")
    parser.add_argument("--brief-input")
    parser.add_argument("--report-output", required=True)
    parser.add_argument("--state-output")
    parser.add_argument("--brief-output")
    args = parser.parse_args()

    history = _load(args.history, {"samples": []})
    state = _load(args.state_input, {})
    brief = _load(args.brief_input, {})
    report, state_out, brief_out = consolidate(history, state, brief)
    _dump(args.report_output, report)
    _dump(args.state_output, state_out)
    _dump(args.brief_output, brief_out)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
