#!/usr/bin/env python3
"""Consolida a confiabilidade contínua do Dashboard UX em modo report-only."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

STABLE = "UX_DASHBOARD_CONTINUOUS_RELIABILITY_STABLE"
REVIEW = "UX_DASHBOARD_CONTINUOUS_RELIABILITY_REVIEW"


def _canonical_fingerprint(sample: dict[str, Any]) -> str:
    contract = {
        "status": sample.get("status"),
        "guardrails_ok": bool(sample.get("guardrails_ok", False)),
        "drift": bool(sample.get("drift", False)),
    }
    raw = json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def build(history: list[dict[str, Any]]) -> dict[str, Any]:
    samples = []
    for item in history:
        normalized = dict(item)
        normalized.setdefault("fingerprint", _canonical_fingerprint(normalized))
        samples.append(normalized)

    total = len(samples)
    healthy = [s for s in samples if s.get("status") == "UX_DASHBOARD_EXECUTIVE_STABILITY_CARD_OK" and s.get("guardrails_ok") is True and not s.get("drift")]
    success_rate = round((len(healthy) / total) * 100, 2) if total else 0.0

    stable_sequence = 0
    for sample in reversed(samples):
        if sample in healthy:
            stable_sequence += 1
        else:
            break

    recent = samples[-3:]
    recurrent_drift = len(recent) == 3 and sum(bool(s.get("drift")) for s in recent) >= 2
    fingerprints = {s.get("fingerprint") for s in healthy if s.get("fingerprint")}
    common_fingerprint = next(iter(fingerprints)) if len(fingerprints) == 1 else None

    eligible = total >= 3 and success_rate == 100.0 and stable_sequence >= 3 and bool(common_fingerprint) and not recurrent_drift
    score = min(100, round(success_rate * 0.7 + min(stable_sequence, 10) * 3, 2))

    return {
        "status": STABLE if eligible else REVIEW,
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
        "samples": total,
        "success_rate": success_rate,
        "stable_sequence": stable_sequence,
        "confidence_score": score,
        "common_fingerprint": common_fingerprint,
        "recurrent_drift": recurrent_drift,
        "eligible_for_human_review": eligible,
    }


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--brief", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    history = _load(args.history)
    result = build(history if isinstance(history, list) else history.get("samples", []))

    state = _load(args.state)
    state.setdefault("cards", {})["user_experience_dashboard_continuous_reliability"] = result
    brief = _load(args.brief)
    brief.setdefault("indicators", {})["user_experience_dashboard_continuous_reliability"] = result

    _write(args.state, state)
    _write(args.brief, brief)
    _write(args.output, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
