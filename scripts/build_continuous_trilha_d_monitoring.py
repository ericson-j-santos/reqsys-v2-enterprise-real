#!/usr/bin/env python3
"""Build Continuous Trilha D Monitoring Index.

Consolida alertas e sinais de regressão automática a partir do histórico Trilha D
e do gate preditivo para consumo pelo dashboard operacional.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = "ericson-j-santos/reqsys-v2-enterprise-real"
DEFAULT_OUTPUT = "docs/ops-dashboard/data/continuous-trilha-d-monitoring.json"
DEFAULT_HISTORY = "docs/ops-dashboard/data/trilha-d-history.json"
DEFAULT_PREDICTIVE = "docs/ops-dashboard/data/predictive-regression-gate.json"
REFRESH_STRATEGY = "artifact_ingestion_on_trilha_d_consolidate"
TRILHA_D_WORKFLOW = "trilha-d-qualidade-governanca.yml"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def workflow_runs_url() -> str:
    return f"https://github.com/{REPO}/actions/workflows/{TRILHA_D_WORKFLOW}"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def build_alerts(
    history: dict[str, Any],
    predictive: dict[str, Any],
) -> list[dict[str, str]]:
    alerts: list[dict[str, str]] = []
    summary = history.get("summary") or {}
    signals = predictive.get("signals") or {}

    if not summary.get("artifact_ingestion_enabled"):
        alerts.append(
            {
                "severity": "warning",
                "code": "artifact_ingestion_disabled",
                "message": "Artifact ingestion ainda não habilitado; monitoramento contínuo em modo degradado.",
            }
        )

    if predictive.get("regression_predicted"):
        alerts.append(
            {
                "severity": "critical",
                "code": "regression_predicted",
                "message": "Gate preditivo sinalizou regressão operacional antes do merge.",
            }
        )

    recent_failed_samples = int(signals.get("recent_failed_samples") or 0)
    if recent_failed_samples > 0:
        alerts.append(
            {
                "severity": "warning",
                "code": "recent_failed_samples",
                "message": f"Trilha D registrou {recent_failed_samples} amostra(s) recente(s) com falha.",
            }
        )

    if str(history.get("trend") or "") == "regressing":
        alerts.append(
            {
                "severity": "critical",
                "code": "overall_trend_regressing",
                "message": "Tendência geral da Trilha D está regredindo.",
            }
        )

    regressing_dimensions = list(signals.get("regressing_dimensions") or [])
    for dimension in regressing_dimensions:
        alerts.append(
            {
                "severity": "warning",
                "code": f"dimension_regressing_{dimension}",
                "message": f"Dimensão {dimension} com tendência de regressão.",
            }
        )

    for reason in predictive.get("blocking_reasons") or []:
        alerts.append(
            {
                "severity": "warning",
                "code": f"predictive_{reason}",
                "message": f"Sinal preditivo: {reason}.",
            }
        )

    if signals.get("projected_drop"):
        alerts.append(
            {
                "severity": "critical",
                "code": "projected_score_drop",
                "message": "Queda projetada de score detectada no relatório consolidado.",
            }
        )

    return alerts


def resolve_monitoring_state(alerts: list[dict[str, str]]) -> str:
    if any(item.get("severity") == "critical" for item in alerts):
        return "red"
    if any(item.get("severity") == "warning" for item in alerts):
        return "yellow"
    return "green"


def resolve_next_increment_from_history(summary: dict[str, Any]) -> str | None:
    from scripts.build_trilha_d_history import resolve_next_increment

    if not summary:
        return None
    artifact_ingestion = bool(summary.get("artifact_ingestion_enabled"))
    return resolve_next_increment(artifact_ingestion=artifact_ingestion)


def build_payload(
    *,
    history_path: Path | None = None,
    predictive_path: Path | None = None,
) -> dict[str, Any]:
    history = load_json(history_path or Path(DEFAULT_HISTORY))
    predictive = load_json(predictive_path or Path(DEFAULT_PREDICTIVE))
    summary = history.get("summary") or {}
    signals = predictive.get("signals") or {}
    alerts = build_alerts(history, predictive)
    state = resolve_monitoring_state(alerts)
    monitoring_enabled = bool(summary.get("artifact_ingestion_enabled"))
    next_increment = resolve_next_increment_from_history(summary) or summary.get("next_increment")

    return {
        "schema_version": "1.0.0",
        "repo": REPO,
        "generated_at": utc_now(),
        "state": state,
        "monitoring_enabled": monitoring_enabled,
        "regression_alert": bool(predictive.get("regression_predicted")) or state == "red",
        "alerts_active": len(alerts),
        "lane": "governance-automation",
        "summary": {
            "next_increment": next_increment,
            "artifact_ingestion_enabled": bool(summary.get("artifact_ingestion_enabled")),
            "continuous_monitoring_enabled": monitoring_enabled,
            "recommendation": "investigar_alertas" if alerts else "monitoramento_estavel",
        },
        "signals": {
            "current_score": history.get("current_score"),
            "baseline_score": history.get("baseline_score"),
            "delta_from_baseline": history.get("delta_from_baseline"),
            "trend": history.get("trend"),
            "predictive_risk": predictive.get("risk"),
            "regression_predicted": bool(predictive.get("regression_predicted")),
            "recent_failed_samples": signals.get("recent_failed_samples", summary.get("failed_samples")),
            "regressing_dimensions": list(signals.get("regressing_dimensions") or []),
            "blocking_reasons": list(predictive.get("blocking_reasons") or []),
        },
        "alerts": alerts,
        "links": {
            "trilha_d": f"https://github.com/{REPO}/blob/main/docs/ops-dashboard/data/trilha-d-history.json",
            "predictive_gate": f"https://github.com/{REPO}/blob/main/docs/ops-dashboard/data/predictive-regression-gate.json",
            "workflow": workflow_runs_url(),
            "source": f"https://github.com/{REPO}/blob/main/scripts/build_continuous_trilha_d_monitoring.py",
            "dashboard_data": f"https://github.com/{REPO}/blob/main/docs/ops-dashboard/data/continuous-trilha-d-monitoring.json",
        },
        "runtime_dashboard_contract": {
            "card_fields": [
                "state",
                "monitoring_enabled",
                "regression_alert",
                "alerts_active",
            ],
            "alert_fields": ["severity", "code", "message"],
            "signal_fields": [
                "trend",
                "predictive_risk",
                "regression_predicted",
                "regressing_dimensions",
            ],
            "refresh_strategy": REFRESH_STRATEGY,
        },
    }


def write_payload(
    output_path: str,
    *,
    history_path: Path | None = None,
    predictive_path: Path | None = None,
) -> dict[str, Any]:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = build_payload(history_path=history_path, predictive_path=predictive_path)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Gera monitoramento contínuo da Trilha D.")
    parser.add_argument("--history", default=DEFAULT_HISTORY)
    parser.add_argument("--predictive", default=DEFAULT_PREDICTIVE)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = write_payload(args.output, history_path=Path(args.history), predictive_path=Path(args.predictive))
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(
            " ".join(
                [
                    f"state={payload['state']}",
                    f"alerts_active={payload['alerts_active']}",
                    f"regression_alert={payload['regression_alert']}",
                    f"next_increment={payload['summary']['next_increment']}",
                ]
            )
        )
    return 0 if payload["state"] != "red" else 1


if __name__ == "__main__":
    raise SystemExit(main())
