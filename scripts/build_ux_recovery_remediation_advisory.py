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

RULES = {
    "recovery_rate_drop": {
        "severity": "high",
        "probable_cause": "ações de recuperação menos eficazes ou contexto vazio sem orientação suficiente",
        "recommended_action": "revisar CTAs, mensagens e telemetria dos contextos com maior queda de recuperação",
        "priority": 1,
    },
    "confidence_drop": {
        "severity": "high",
        "probable_cause": "redução combinada da qualidade ou suficiência das evidências UX",
        "recommended_action": "validar amostras recentes, integridade do encadeamento e critérios de prontidão",
        "priority": 2,
    },
    "recovery_time_increase": {
        "severity": "medium",
        "probable_cause": "fricção adicional no caminho até a ação de recuperação",
        "recommended_action": "inspecionar latência percebida, clareza da ação principal e etapas intermediárias",
        "priority": 3,
    },
    "qualified_sequence_break": {
        "severity": "medium",
        "probable_cause": "uma execução recente deixou de atender os critérios qualificados",
        "recommended_action": "comparar a execução atual com a última qualificada e corrigir o contexto regressivo",
        "priority": 4,
    },
}


def build_recommendations(report: dict[str, Any]) -> list[dict[str, Any]]:
    latest = report.get("latest") if isinstance(report.get("latest"), dict) else {}
    deltas = report.get("deltas") if isinstance(report.get("deltas"), dict) else {}
    recommendations = []
    for alert in report.get("alerts", []):
        rule = RULES.get(alert)
        if not rule:
            continue
        recommendations.append({
            "alert": alert,
            **rule,
            "evidence": {
                "source_run_id": latest.get("source_run_id"),
                "source_head_sha": latest.get("source_head_sha"),
                "generated_at": latest.get("generated_at"),
                "delta": deltas,
            },
        })
    return sorted(recommendations, key=lambda item: item["priority"])


def consolidate(dashboard: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(dashboard) if isinstance(dashboard, dict) else {}
    cards = result.get("cards") if isinstance(result.get("cards"), list) else []
    output_cards = []
    found = False
    recommendations = build_recommendations(report)
    for item in cards:
        if isinstance(item, dict) and item.get("id") == CARD_ID:
            updated = deepcopy(item)
            updated["regression"] = {
                "status": report.get("status", "UX_RECOVERY_TREND_STABLE"),
                "detected": report.get("regression_detected") is True,
                "alerts": report.get("alerts", []),
                "deltas": report.get("deltas", {}),
                "recommendations": recommendations,
                "highest_severity": recommendations[0]["severity"] if recommendations else "none",
                "mode": "advisory",
                "production_blocker": False,
                "human_approval_required": True,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
            output_cards.append(updated)
            found = True
        else:
            output_cards.append(item)
    if not found:
        raise ValueError(f"card {CARD_ID} não encontrado")
    result["cards"] = output_cards
    result["schema_version"] = result.get("schema_version", SCHEMA_VERSION)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard", required=True, type=Path)
    parser.add_argument("--regression", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    dashboard = json.loads(args.dashboard.read_text(encoding="utf-8"))
    regression = json.loads(args.regression.read_text(encoding="utf-8"))
    output = consolidate(dashboard, regression)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    card = next(item for item in output["cards"] if item.get("id") == CARD_ID)
    print(json.dumps(card["regression"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
