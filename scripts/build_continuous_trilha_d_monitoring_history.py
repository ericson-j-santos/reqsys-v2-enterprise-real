#!/usr/bin/env python3
"""Build Continuous Trilha D Monitoring History Index.

Agrega snapshots do monitoramento contínuo para medir estabilidade operacional:
- taxa de alertas ativos;
- tendência de estado green/yellow/red;
- regressões preditivas recentes.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = "ericson-j-santos/reqsys-v2-enterprise-real"
DEFAULT_OUTPUT = "docs/ops-dashboard/data/continuous-trilha-d-monitoring-history.json"
DEFAULT_MONITORING = "docs/ops-dashboard/data/continuous-trilha-d-monitoring.json"
TRILHA_D_WORKFLOW = "trilha-d-qualidade-governanca.yml"
MAX_SAMPLES = 60


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


def load_history(path: Path) -> list[dict[str, Any]]:
    payload = load_json(path)
    history = payload.get("history")
    if isinstance(history, list):
        return history
    return []


def snapshot_from_monitoring(
    monitoring: dict[str, Any],
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    summary = monitoring.get("summary") or {}
    signals = monitoring.get("signals") or {}
    return {
        "timestamp": utc_now(),
        "run_id": run_id or "",
        "state": monitoring.get("state", "unknown"),
        "alerts_active": int(monitoring.get("alerts_active") or 0),
        "regression_alert": bool(monitoring.get("regression_alert")),
        "monitoring_enabled": bool(monitoring.get("monitoring_enabled")),
        "recommendation": summary.get("recommendation", ""),
        "predictive_risk": signals.get("predictive_risk"),
        "trend": signals.get("trend"),
        "workflow_run_url": (
            f"https://github.com/{REPO}/actions/runs/{run_id}" if run_id and run_id.isdigit() else workflow_runs_url()
        ),
    }


def merge_history(existing: list[dict[str, Any]], snapshot: dict[str, Any], *, max_samples: int = MAX_SAMPLES) -> list[dict[str, Any]]:
    run_id = snapshot.get("run_id")
    if run_id:
        history = [item for item in existing if item.get("run_id") != run_id]
    else:
        history = list(existing)
    history.append(snapshot)
    return history[-max_samples:]


def build_metrics(history: list[dict[str, Any]]) -> dict[str, Any]:
    if not history:
        return {
            "samples": 0,
            "green_rate": 0.0,
            "yellow_rate": 0.0,
            "red_rate": 0.0,
            "avg_alerts_active": 0.0,
            "regression_alert_rate": 0.0,
            "stable_samples": 0,
            "alerting_samples": 0,
            "state_distribution": [],
        }

    state_counter: Counter[str] = Counter(str(item.get("state") or "unknown") for item in history)
    regression_samples = sum(1 for item in history if item.get("regression_alert"))
    alerting_samples = sum(1 for item in history if int(item.get("alerts_active") or 0) > 0)
    stable_samples = len(history) - alerting_samples

    return {
        "samples": len(history),
        "green_rate": round(state_counter.get("green", 0) / len(history), 4),
        "yellow_rate": round(state_counter.get("yellow", 0) / len(history), 4),
        "red_rate": round(state_counter.get("red", 0) / len(history), 4),
        "avg_alerts_active": round(sum(int(item.get("alerts_active") or 0) for item in history) / len(history), 2),
        "regression_alert_rate": round(regression_samples / len(history), 4),
        "stable_samples": stable_samples,
        "alerting_samples": alerting_samples,
        "state_distribution": [
            {"state": state, "count": count}
            for state, count in state_counter.most_common()
        ],
    }


def build_payload(
    history: list[dict[str, Any]],
    *,
    continuous_trilha_d_monitoring_history_enabled: bool = True,
) -> dict[str, Any]:
    metrics = build_metrics(history)
    latest = history[-1] if history else {}
    state = "green"
    if metrics["red_rate"] >= 0.25:
        state = "red"
    elif metrics["yellow_rate"] > 0 or metrics["alerting_samples"] > 0:
        state = "yellow"

    recommendation = "monitoramento_estavel"
    if latest.get("state") == "red" or metrics["red_rate"] > 0:
        recommendation = "investigar_regressao_critica"
    elif latest.get("state") == "yellow" or metrics["alerting_samples"] > 0:
        recommendation = "investigar_alertas"

    return {
        "schema_version": "1.0.0",
        "repo": REPO,
        "generated_at": utc_now(),
        "state": state,
        "summary": {
            "continuous_trilha_d_monitoring_history_enabled": continuous_trilha_d_monitoring_history_enabled,
            "samples": metrics["samples"],
            "green_rate": metrics["green_rate"],
            "avg_alerts_active": metrics["avg_alerts_active"],
            "monitoring_stabilized": latest.get("state") == "green" and int(latest.get("alerts_active") or 0) == 0,
            "recommendation": recommendation,
        },
        "metrics": metrics,
        "latest_snapshot": latest,
        "history": history,
        "links": {
            "workflow": workflow_runs_url(),
            "monitoring": f"https://github.com/{REPO}/blob/main/{DEFAULT_MONITORING}",
            "source": f"https://github.com/{REPO}/blob/main/scripts/build_continuous_trilha_d_monitoring_history.py",
            "dashboard_data": f"https://github.com/{REPO}/blob/main/{DEFAULT_OUTPUT}",
        },
        "runtime_dashboard_contract": {
            "card_fields": [
                "state",
                "green_rate",
                "avg_alerts_active",
                "samples",
            ],
            "history_fields": [
                "timestamp",
                "state",
                "alerts_active",
                "regression_alert",
                "recommendation",
                "workflow_run_url",
            ],
            "refresh_strategy": "artifact_ingestion_on_trilha_d_consolidate",
        },
    }


def ingest_monitoring_snapshot(
    monitoring_path: str,
    output_path: str,
    *,
    run_id: str | None = None,
    max_samples: int = MAX_SAMPLES,
) -> dict[str, Any]:
    monitoring = load_json(Path(monitoring_path))
    output = Path(output_path)
    existing = load_history(output)
    snapshot = snapshot_from_monitoring(monitoring, run_id=run_id)
    history = merge_history(existing, snapshot, max_samples=max_samples)
    payload = build_payload(history)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def write_payload(output_path: str, *, history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = build_payload(history or [])
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Gera continuous-trilha-d-monitoring-history.json para o dashboard operacional.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--ingest-monitoring", help="JSON do monitoramento contínuo para append no histórico")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--max-samples", type=int, default=MAX_SAMPLES)
    parser.add_argument("--json", action="store_true", help="Imprime o payload gerado")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.ingest_monitoring:
        payload = ingest_monitoring_snapshot(
            args.ingest_monitoring,
            args.output,
            run_id=args.run_id or None,
            max_samples=args.max_samples,
        )
    else:
        payload = write_payload(args.output)
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(
            "continuous_trilha_d_monitoring_history_state="
            f"{payload['state']} samples={payload['summary']['samples']} output={args.output}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
