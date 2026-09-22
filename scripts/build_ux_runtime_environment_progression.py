#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from statistics import mean
from typing import Any

CARD_ID = "ux-runtime-environment-progression"
ENVIRONMENTS = ("dev", "stg", "prod")


def build_progression(history: list[dict[str, Any]] | None) -> dict[str, Any]:
    verified = [
        item for item in (history or [])
        if isinstance(item, dict)
        and item.get("evidence_source") == "runtime"
        and item.get("verification_status") == "verified"
        and item.get("environment") in ENVIRONMENTS
    ]
    environments: dict[str, dict[str, Any]] = {}
    previous_ready = True
    for environment in ENVIRONMENTS:
        samples = [item for item in verified if item.get("environment") == environment]
        rates = [float(item.get("recovery_rate", 0) or 0) for item in samples]
        times = [float(item.get("average_recovery_seconds", 0) or 0) for item in samples]
        ready_runs = sum(1 for item in samples if item.get("ux_100_ready") is True)
        sample_count = len(samples)
        stable = sample_count >= 3 and ready_runs >= 2 and mean(rates) >= 60 and mean(times) <= 30
        eligible = previous_ready and stable
        if sample_count == 0:
            status = "NO_RUNTIME_EVIDENCE"
        elif not stable:
            status = "RUNTIME_OBSERVED"
        elif not previous_ready:
            status = "WAITING_PREVIOUS_ENVIRONMENT"
        else:
            status = "READY_FOR_HUMAN_REVIEW"
        environments[environment] = {
            "status": status,
            "samples": sample_count,
            "ready_runs": ready_runs,
            "average_recovery_rate": round(mean(rates), 1) if rates else 0.0,
            "average_recovery_seconds": round(mean(times), 1) if times else 0.0,
            "stable": stable,
            "eligible_for_human_review": eligible,
        }
        previous_ready = previous_ready and stable

    return {
        "id": CARD_ID,
        "title": "Progressão de evidência runtime por ambiente",
        "sequence": list(ENVIRONMENTS),
        "environments": environments,
        "current_stage": next((env for env in ENVIRONMENTS if not environments[env]["eligible_for_human_review"]), "prod"),
        "mode": "advisory",
        "production_blocker": False,
        "human_approval_required": True,
        "automatic_promotion": False,
    }


def publish_dashboard(dashboard: dict[str, Any], card: dict[str, Any]) -> dict[str, Any]:
    output = deepcopy(dashboard) if isinstance(dashboard, dict) else {}
    cards = output.get("cards", [])
    cards = cards if isinstance(cards, list) else []
    output["cards"] = [
        item for item in cards
        if not (isinstance(item, dict) and item.get("id") == CARD_ID)
    ] + [card]
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", required=True, type=Path)
    parser.add_argument("--dashboard", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    history = json.loads(args.history.read_text(encoding="utf-8")) if args.history.exists() else []
    dashboard = json.loads(args.dashboard.read_text(encoding="utf-8")) if args.dashboard.exists() else {}
    card = build_progression(history if isinstance(history, list) else [])
    dashboard_out = publish_dashboard(dashboard if isinstance(dashboard, dict) else {}, card)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "ux-runtime-environment-progression.json").write_text(json.dumps(card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "ops-dashboard.json").write_text(json.dumps(dashboard_out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
