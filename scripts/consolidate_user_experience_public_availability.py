#!/usr/bin/env python3
"""Consolida a disponibilidade pública de UX no Estado Único e Executive Brief.

Mantém todos os guardrails em modo report-only e nunca altera readiness,
production_ready ou deploy.
"""
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

REQUIRED_ENVS = {"dev", "stg", "prod"}
MIN_HEALTHY_SAMPLES = 3
MIN_AVAILABILITY = 100.0


def _load(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return deepcopy(default)
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def consolidate(evidence: dict[str, Any], state: dict[str, Any], brief: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    environments = evidence.get("environments") or {}
    covered = set(environments)
    rates = {name: float((data or {}).get("pass_rate", 0.0)) for name, data in environments.items()}
    minimum_rate = min(rates.values()) if rates else 0.0
    sample_count = int(evidence.get("sample_count", 0))
    stable_sequence = int(evidence.get("stable_sequence", 0))
    drift = bool(evidence.get("drift_detected", True))
    degradation = bool(evidence.get("degradation_detected", True))
    common_fingerprint = evidence.get("common_fingerprint")
    complete = REQUIRED_ENVS.issubset(covered)

    eligible = bool(
        complete
        and minimum_rate >= MIN_AVAILABILITY
        and sample_count >= MIN_HEALTHY_SAMPLES
        and stable_sequence >= MIN_HEALTHY_SAMPLES
        and common_fingerprint
        and not drift
        and not degradation
    )

    status = "PUBLIC_AVAILABILITY_STABLE" if eligible else "PUBLIC_AVAILABILITY_REVIEW"
    indicator = {
        "status": status,
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
        "coverage_complete": complete,
        "environments": environments,
        "minimum_pass_rate": minimum_rate,
        "sample_count": sample_count,
        "stable_sequence": stable_sequence,
        "common_fingerprint": common_fingerprint,
        "drift_detected": drift,
        "degradation_detected": degradation,
        "human_review_eligible": eligible,
        "thresholds": {
            "minimum_pass_rate": MIN_AVAILABILITY,
            "minimum_samples": MIN_HEALTHY_SAMPLES,
            "minimum_stable_sequence": MIN_HEALTHY_SAMPLES,
        },
    }

    new_state = deepcopy(state)
    new_brief = deepcopy(brief)
    new_state.setdefault("cards", {})["user_experience_public_availability"] = indicator
    new_brief.setdefault("indicators", {})["user_experience_public_availability"] = indicator
    return new_state, new_brief


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--brief", type=Path, required=True)
    args = parser.parse_args()

    evidence = _load(args.evidence, {})
    state = _load(args.state, {})
    brief = _load(args.brief, {})
    new_state, new_brief = consolidate(evidence, state, brief)
    _write(args.state, new_state)
    _write(args.brief, new_brief)
    print(new_state["cards"]["user_experience_public_availability"]["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
