#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from statistics import mean
from typing import Any

CARD_ID = "ux-recovery-evidence-maturity"


def evaluate(history: list[dict[str, Any]] | None) -> dict[str, Any]:
    records = [item for item in (history or []) if isinstance(item, dict)]
    runtime = [item for item in records if item.get("evidence_source") == "runtime"]
    ready = [item for item in runtime if item.get("ux_100_ready") is True]
    rates = [float(item.get("recovery_rate", 0) or 0) for item in runtime]
    times = [float(item.get("average_recovery_seconds", 0) or 0) for item in runtime]

    if not runtime:
        status = "UX_EVIDENCE_SYNTHETIC_ONLY"
    elif len(runtime) < 3:
        status = "UX_EVIDENCE_INITIAL"
    elif len(runtime) >= 5 and len(ready) >= 3 and mean(rates) >= 60 and mean(times) <= 30:
        status = "UX_EVIDENCE_GOLD_READY"
    else:
        status = "UX_EVIDENCE_SUFFICIENT"

    return {
        "id": CARD_ID,
        "title": "Maturidade da evidência de recuperação UX",
        "status": status,
        "runtime_runs": len(runtime),
        "synthetic_runs": len(records) - len(runtime),
        "ready_runs": len(ready),
        "average_recovery_rate": round(mean(rates), 1) if rates else 0.0,
        "average_recovery_seconds": round(mean(times), 1) if times else 0.0,
        "gold_ready": status == "UX_EVIDENCE_GOLD_READY",
        "criteria": {
            "minimum_runtime_runs": len(runtime) >= 5,
            "minimum_ready_runs": len(ready) >= 3,
            "recovery_rate_at_least_60": bool(rates) and mean(rates) >= 60,
            "average_recovery_at_most_30s": bool(times) and mean(times) <= 30,
        },
        "mode": "advisory",
        "production_blocker": False,
        "human_approval_required": True,
    }


def publish_dashboard(dashboard: dict[str, Any], indicator: dict[str, Any]) -> dict[str, Any]:
    output = deepcopy(dashboard) if isinstance(dashboard, dict) else {}
    cards = output.get("cards", [])
    cards = cards if isinstance(cards, list) else []
    output["cards"] = [
        card for card in cards
        if not (isinstance(card, dict) and card.get("id") == CARD_ID)
    ] + [indicator]
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", required=True, type=Path)
    parser.add_argument("--dashboard", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    history = json.loads(args.history.read_text(encoding="utf-8"))
    dashboard = json.loads(args.dashboard.read_text(encoding="utf-8"))
    indicator = evaluate(history if isinstance(history, list) else [])
    dashboard_out = publish_dashboard(dashboard, indicator)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "ux-recovery-evidence-maturity.json").write_text(
        json.dumps(indicator, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "ops-dashboard.json").write_text(
        json.dumps(dashboard_out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
