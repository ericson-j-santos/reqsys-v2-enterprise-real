#!/usr/bin/env python3
"""Operational Observability Hub — consolidates multi-env evidence, drift, SLO,
longitudinal analytics, governed alerts and CI↔runtime↔observability correlation.

Report-only orchestrator; chains existing generators and emits a unified artifact.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def run_script(script: str, *args: str) -> int:
    cmd = [sys.executable, str(ROOT / script), *args]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr or result.stdout, file=sys.stderr)
    return result.returncode


def build_correlation_chain(
    runs: list[dict[str, Any]],
    history: list[dict[str, Any]],
    coordenador: dict[str, Any],
    multi_env: dict[str, Any],
    workflow_run_id: str | None,
    commit_sha: str,
    correlation_id: str,
) -> list[dict[str, Any]]:
    chain: list[dict[str, Any]] = []
    seq = 1

    if runs:
        latest_ci = runs[0]
        chain.append(
            {
                "sequence": seq,
                "event": "ci_workflow_run",
                "source": "github_actions",
                "correlation_level": "ci",
                "workflow_run_id": latest_ci.get("databaseId") or workflow_run_id,
                "workflow_name": latest_ci.get("workflowName") or latest_ci.get("name"),
                "conclusion": latest_ci.get("conclusion"),
                "head_sha": latest_ci.get("headSha") or commit_sha,
                "correlation_id": correlation_id,
            }
        )
        seq += 1

    if coordenador:
        chain.append(
            {
                "sequence": seq,
                "event": "coordenador_status_captured",
                "source": "coordenador-status-consolidator",
                "correlation_level": "governance",
                "state": coordenador.get("state"),
                "decision": coordenador.get("decision"),
                "correlation_id": coordenador.get("correlation_id") or correlation_id,
            }
        )
        seq += 1

    if history:
        latest = history[-1]
        chain.append(
            {
                "sequence": seq,
                "event": "operational_history_snapshot",
                "source": "operational-center-history",
                "correlation_level": "analytics",
                "hub_score": latest.get("hub_score"),
                "mttr_minutes": (latest.get("metrics") or {}).get("mttr_minutes"),
                "correlation_id": correlation_id,
            }
        )
        seq += 1

    for env in multi_env.get("environments") or []:
        if env.get("canonical") in {"dev", "hml", "prod"}:
            chain.append(
                {
                    "sequence": seq,
                    "event": "environment_probe",
                    "source": "multi-environment-evidence",
                    "correlation_level": "runtime",
                    "environment": env.get("canonical"),
                    "status": env.get("status"),
                    "readiness_percent": env.get("readiness_percent"),
                    "correlation_id": correlation_id,
                }
            )
            seq += 1

    return chain


def classify_alert(
    drift: dict[str, Any],
    slo: dict[str, Any],
    longitudinal: dict[str, Any],
) -> dict[str, Any]:
    alert_level = "INFO"
    alert_type = "OPERATIONAL_SIGNAL"
    noise_level = "LOW"
    action_policy = "OBSERVE"
    should_alert = True

    if drift.get("drift_level") in {"ALTO", "MEDIO"}:
        alert_level = "HIGH" if drift.get("drift_level") == "ALTO" else "MEDIUM"
        alert_type = "ENVIRONMENT_DRIFT"
        action_policy = "MANUAL_REVIEW_REQUIRED"

    breach_count = (slo.get("summary") or {}).get("breach_count") or 0
    if breach_count >= 2:
        alert_level = "HIGH"
        alert_type = "SLO_BREACH"
        action_policy = "MANUAL_REVIEW_REQUIRED"
    elif breach_count == 1 and alert_level == "INFO":
        alert_level = "MEDIUM"
        alert_type = "SLO_WATCH"

    if longitudinal.get("trend", {}).get("direction") == "piorando" and alert_level == "INFO":
        alert_level = "MEDIUM"
        alert_type = "LONGITUDINAL_DEGRADATION"
        action_policy = "VERIFY_CONTEXT"

    if alert_level == "INFO" and breach_count == 0 and drift.get("drift_level") == "NENHUM":
        noise_level = "SUPPRESSED"
        should_alert = False

    return {
        "alert_level": alert_level,
        "alert_type": alert_type,
        "noise_level": noise_level,
        "action_policy": action_policy,
        "should_alert": should_alert,
        "mode": "governed_report_only",
    }


def consolidate_hub(
    multi_env: dict[str, Any],
    drift: dict[str, Any],
    slo: dict[str, Any],
    longitudinal: dict[str, Any],
    history_index: dict[str, Any],
    correlation_chain: list[dict[str, Any]],
    alert: dict[str, Any],
    repository: str,
    commit_sha: str,
    workflow_run_id: str | None,
    correlation_id: str,
) -> dict[str, Any]:
    risks = [
        multi_env.get("operational_risk"),
        drift.get("operational_risk"),
        slo.get("operational_risk"),
        longitudinal.get("operational_risk"),
    ]
    if "high" in risks:
        status, risk = "degraded", "high"
    elif "medium" in risks:
        status, risk = "watch", "medium"
    else:
        status, risk = "healthy", "low"

    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "operational-observability-hub",
        "status": status,
        "confidence_level": "high" if correlation_chain else "medium",
        "maturity_percent": longitudinal.get("maturity_percent", 0),
        "operational_risk": risk,
        "commit_sha": commit_sha,
        "workflow_run_id": workflow_run_id,
        "correlation_id": correlation_id,
        "repository": repository,
        "mode": "report_only",
        "pareto_increment": {
            "multi_environment_evidence": True,
            "metrics_history_persisted": history_index.get("summary", {}).get("snapshot_count", 0) > 0,
            "longitudinal_analytics": longitudinal.get("history_points_total", 0) > 0,
            "environment_drift_detection": drift.get("drift_level") is not None,
            "governed_alerts": alert.get("should_alert") is not None,
            "slo_sla_evidence": (slo.get("summary") or {}).get("slo_count", 0) > 0,
            "ci_runtime_observability_correlation": len(correlation_chain) > 0,
        },
        "sources": {
            "multi_environment": multi_env.get("summary"),
            "environment_drift": {"drift_level": drift.get("drift_level"), "findings": len(drift.get("findings") or [])},
            "slo_evidence": slo.get("summary"),
            "longitudinal": {"windows": longitudinal.get("windows"), "trend": longitudinal.get("trend")},
            "history_index": history_index.get("summary"),
        },
        "governed_alert": alert,
        "correlation_chain": correlation_chain,
        "recommended_actions": _recommended_actions(drift, slo, longitudinal, alert),
        "guardrails": [
            "report_only",
            "no_auto_deploy",
            "no_production_mutation",
            "human_review_required",
        ],
    }


def _recommended_actions(
    drift: dict[str, Any],
    slo: dict[str, Any],
    longitudinal: dict[str, Any],
    alert: dict[str, Any],
) -> list[str]:
    actions: list[str] = []
    actions.extend(drift.get("recommendations") or [])
    for slo_item in slo.get("slos") or []:
        if slo_item.get("breach"):
            actions.append(f"Tratar breach SLO {slo_item['slo_id']}: actual={slo_item.get('actual_percent')}%")
    if longitudinal.get("trend", {}).get("direction") == "piorando":
        actions.append("Revisar tendencia longitudinal degradante nos ultimos snapshots.")
    if alert.get("should_alert"):
        actions.append(f"Alerta governado {alert['alert_level']}: {alert['alert_type']} — {alert['action_policy']}")
    if not actions:
        actions.append("Hub saudavel — continuar ciclo operacional e monitoramento agendado.")
    return actions[:10]


def render_markdown(report: dict[str, Any]) -> str:
    pareto = report.get("pareto_increment") or {}
    lines = [
        "# Operational Observability Hub",
        "",
        f"- Correlation ID: `{report['correlation_id']}`",
        f"- Status: `{report['status']}`",
        f"- Risk: `{report['operational_risk']}`",
        f"- Correlation chain events: `{len(report.get('correlation_chain') or [])}`",
        "",
        "## Pareto increment",
        "",
    ]
    for key, value in pareto.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Governed alert", ""])
    alert = report.get("governed_alert") or {}
    lines.append(f"- Level: `{alert.get('alert_level')}` · Type: `{alert.get('alert_type')}` · Policy: `{alert.get('action_policy')}`")
    lines.extend(["", "## Recommended actions", ""])
    lines.extend(f"- {action}" for action in report.get("recommended_actions") or [])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Operational Observability Hub consolidator.")
    parser.add_argument("--repository", default="local/reqsys")
    parser.add_argument("--commit-sha", default="local")
    parser.add_argument("--workflow-run-id", default="")
    parser.add_argument("--correlation-id", default="")
    parser.add_argument("--skip-probes", action="store_true", help="Skip live environment probes")
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/operational-observability-hub"))
    args = parser.parse_args()

    correlation_id = args.correlation_id or str(uuid4())
    common = ["--commit-sha", args.commit_sha, "--correlation-id", correlation_id]

    if not args.skip_probes:
        run_script("scripts/validate_environments_readiness.py")

    run_script("scripts/operational_multi_environment_evidence.py", *common)
    run_script("scripts/environment_drift_analyzer.py", *common[:2])
    run_script("scripts/generate_operational_slo_evidence.py", *common)
    run_script("scripts/operational_longitudinal_analytics.py", "--commit-sha", args.commit_sha)
    run_script(
        "scripts/build_operational_history_index.py",
        "--repository",
        args.repository,
    )

    multi_env = load_json(Path("artifacts/operational-multi-environment/multi-environment-evidence.json"), {})
    drift = load_json(Path("artifacts/environment-drift-analyzer/environment-drift.json"), {})
    slo = load_json(Path("artifacts/operational-slo-evidence/operational-slo-evidence.json"), {})
    longitudinal = load_json(
        Path("artifacts/operational-longitudinal-analytics/longitudinal-analytics.json"), {}
    )
    history_index = load_json(Path("artifacts/operational-history-index/operational-history-index.json"), {})
    history = load_json(Path("artifacts/operational-history/operational-history.json"), [])
    if not isinstance(history, list):
        history = []
    runs = load_json(Path("artifacts/operational-health/runs.json"), [])
    if not isinstance(runs, list):
        runs = []
    coordenador = load_json(Path("artifacts/coordenador-status/coordenador-status.json"), {})

    correlation_chain = build_correlation_chain(
        runs,
        history,
        coordenador,
        multi_env,
        args.workflow_run_id or None,
        args.commit_sha,
        correlation_id,
    )
    alert = classify_alert(drift, slo, longitudinal)
    report = consolidate_hub(
        multi_env,
        drift,
        slo,
        longitudinal,
        history_index,
        correlation_chain,
        alert,
        args.repository,
        args.commit_sha,
        args.workflow_run_id or None,
        correlation_id,
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "operational-observability-hub.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (args.out_dir / "operational-observability-hub.md").write_text(render_markdown(report), encoding="utf-8")

    timeline_dir = ROOT / "reports" / "github-runtime-analytics"
    timeline_dir.mkdir(parents=True, exist_ok=True)
    timeline_payload = {
        "schema_version": "1.1.0",
        "generated_at": report["generated_at"],
        "name": "runtime-operational-correlation-timeline",
        "mode": "report_only",
        "runtime_state": "TIMELINE_HYDRATED",
        "correlation_id": correlation_id,
        "workflow_run_id": args.workflow_run_id or None,
        "timeline_event_count": len(correlation_chain),
        "timeline": correlation_chain,
        "confidence_percent": 85 if correlation_chain else 40,
        "risk_percent": 60 if report["operational_risk"] == "high" else 20,
        "limits": report["guardrails"],
    }
    (timeline_dir / "runtime-operational-correlation-timeline.json").write_text(
        json.dumps(timeline_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(render_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
