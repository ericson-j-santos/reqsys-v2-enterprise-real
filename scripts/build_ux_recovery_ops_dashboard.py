#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CARD_ID = "ux-recovery-standard-gold-readiness"
SCHEMA_VERSION = "1.0.0"


def _confidence(sample_count: int, consecutive: int, ready: bool) -> int:
    sample_score = min(sample_count / 3, 1.0) * 55
    sequence_score = min(consecutive / 2, 1.0) * 35
    readiness_score = 10 if ready else 0
    return round(sample_score + sequence_score + readiness_score)


def _gap(stability: dict[str, Any]) -> list[str]:
    criteria = stability.get("criteria") if isinstance(stability.get("criteria"), dict) else {}
    gaps: list[str] = []
    sample_count = int(stability.get("sample_count", 0))
    consecutive = int(stability.get("consecutive_qualified_samples", 0))
    required_samples = int(criteria.get("minimum_samples", 3))
    required_consecutive = int(criteria.get("minimum_consecutive_qualified", 2))
    if sample_count < required_samples:
        gaps.append(f"coletar mais {required_samples - sample_count} amostra(s)")
    if consecutive < required_consecutive:
        gaps.append(f"obter mais {required_consecutive - consecutive} evidência(s) qualificada(s) consecutiva(s)")
    return gaps or ["nenhuma lacuna técnica; aguarda aprovação humana"]


def build_card(history: list[dict[str, Any]] | None, stability: dict[str, Any]) -> dict[str, Any]:
    samples = [item for item in (history or []) if isinstance(item, dict)]
    latest = samples[-1] if samples else {}
    sample_count = int(stability.get("sample_count", len(samples)))
    consecutive = int(stability.get("consecutive_qualified_samples", 0))
    ready = stability.get("standard_gold_ready") is True
    return {
        "id": CARD_ID,
        "schema_version": SCHEMA_VERSION,
        "title": "Prontidão padrão ouro — recuperação UX",
        "status": stability.get("status", "UX_STABILITY_EVIDENCE_PENDING"),
        "standard_gold_ready": ready,
        "sample_count": sample_count,
        "qualified_sample_count": int(stability.get("qualified_sample_count", 0)),
        "consecutive_qualified_samples": consecutive,
        "confidence_percent": _confidence(sample_count, consecutive, ready),
        "recovery_rate_average": float(stability.get("recovery_rate_average", 0)),
        "recovery_seconds_average": float(stability.get("recovery_seconds_average", 0)),
        "latest_evidence": {
            "source_run_id": latest.get("source_run_id"),
            "source_head_sha": latest.get("source_head_sha"),
            "source_workflow": latest.get("source_workflow"),
            "generated_at": latest.get("generated_at"),
        },
        "remaining_gap": _gap(stability),
        "mode": "advisory",
        "production_blocker": False,
        "human_approval_required": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def consolidate_dashboard(dashboard: dict[str, Any] | None, card: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(dashboard) if isinstance(dashboard, dict) else {}
    cards = result.get("cards") if isinstance(result.get("cards"), list) else []
    result["cards"] = [item for item in cards if not (isinstance(item, dict) and item.get("id") == CARD_ID)] + [card]
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", required=True, type=Path)
    parser.add_argument("--stability", required=True, type=Path)
    parser.add_argument("--dashboard", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    history = json.loads(args.history.read_text(encoding="utf-8"))
    stability = json.loads(args.stability.read_text(encoding="utf-8"))
    if not isinstance(history, list):
        raise ValueError("history deve ser uma lista JSON")
    if not isinstance(stability, dict):
        raise ValueError("stability deve ser um objeto JSON")
    dashboard = {}
    if args.dashboard and args.dashboard.exists():
        dashboard = json.loads(args.dashboard.read_text(encoding="utf-8"))
    card = build_card(history, stability)
    output = consolidate_dashboard(dashboard, card)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"card": CARD_ID, "confidence_percent": card["confidence_percent"], "gap": card["remaining_gap"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
