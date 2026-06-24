#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_MIN_SCORE = 70
DEFAULT_MIN_CONFIDENCE = "media"
CONFIDENCE_ORDER = {"baixa": 1, "media": 2, "alta": 3}


def load_json(path: Path, default: dict | list):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_gate(report: dict, history: list, min_score: int, min_confidence: str) -> dict:
    hub = report.get("hub_score", {})
    score = float(hub.get("score") or 0)
    confidence = str(hub.get("confidence") or "baixa")
    status = str(hub.get("status") or "SEM_DADOS")

    reasons = []
    blocked = False

    if score < min_score:
        blocked = True
        reasons.append(f"Score operacional abaixo do limite minimo: {score} < {min_score}")

    if CONFIDENCE_ORDER.get(confidence, 0) < CONFIDENCE_ORDER.get(min_confidence, 0):
        blocked = True
        reasons.append(f"Confianca insuficiente: {confidence}")

    recent_failures = 0
    for item in history[-10:]:
        metrics = item.get("metrics", {})
        if float(metrics.get("overall_failure_rate_percent") or 0) >= 40:
            recent_failures += 1

    if recent_failures >= 3:
        blocked = True
        reasons.append("Recorrencia elevada de falhas nos ultimos snapshots")

    if not report.get("available_layers"):
        blocked = True
        reasons.append("Nenhuma camada operacional disponivel")

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "gate_status": "BLOCKED" if blocked else "APPROVED",
        "hub_status": status,
        "hub_score": score,
        "hub_confidence": confidence,
        "minimum_score_required": min_score,
        "minimum_confidence_required": min_confidence,
        "recent_failure_snapshots": recent_failures,
        "reasons": reasons,
        "allowed_actions": [
            "generate_artifacts",
            "collect_evidence",
            "manual_review"
        ],
        "blocked_actions": [
            "auto_merge",
            "auto_rerun",
            "deploy_without_review",
            "bypass_ci"
        ]
    }


def render_markdown(result: dict) -> str:
    lines = [
        "# Operational Governance Gate",
        "",
        f"Atualizado em UTC: `{result['generated_at_utc']}`",
        "",
        f"- Gate: `{result['gate_status']}`",
        f"- Status operacional: `{result['hub_status']}`",
        f"- Score operacional: `{result['hub_score']}`",
        f"- Confiança: `{result['hub_confidence']}`",
        "",
        "## Motivos",
        ""
    ]
    if result['reasons']:
        lines.extend([f"- {item}" for item in result['reasons']])
    else:
        lines.append("- Nenhum bloqueio identificado.")

    lines.extend([
        "",
        "## Ações bloqueadas",
        ""
    ])
    lines.extend([f"- `{item}`" for item in result['blocked_actions']])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="ReqSys Operational Governance Gate")
    parser.add_argument("--hub", type=Path, default=Path("artifacts/operational-intelligence-hub/operational-intelligence-hub.json"))
    parser.add_argument("--history", type=Path, default=Path("artifacts/operational-history/operational-history.json"))
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/operational-governance-gate"))
    parser.add_argument("--min-score", type=int, default=DEFAULT_MIN_SCORE)
    parser.add_argument("--min-confidence", type=str, default=DEFAULT_MIN_CONFIDENCE)
    args = parser.parse_args()

    report = load_json(args.hub, {})
    history = load_json(args.history, [])
    result = evaluate_gate(report, history, args.min_score, args.min_confidence)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "operational-governance-gate.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.out_dir / "operational-governance-gate.md").write_text(render_markdown(result), encoding="utf-8")
    print(render_markdown(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
