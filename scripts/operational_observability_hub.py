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


def load_contract_artifacts(
    contract_index_path: Path,
    openapi_validation_path: Path,
    openapi_semantic_diff_path: Path,
) -> dict[str, Any]:
    contract_index = load_json(contract_index_path, {})
    openapi_validation = load_json(openapi_validation_path, {})
    semantic_diff = load_json(openapi_semantic_diff_path, {})

    semantic_drift_count = int((semantic_diff.get("summary") or {}).get("drift_count") or 0)
    validation_status = str(openapi_validation.get("status") or "unknown")
    traceability = contract_index.get("traceability") or {}
    openapi_to_ci = traceability.get("openapi_to_ci") or {}

    hydrated = bool(contract_index) or bool(openapi_validation) or bool(semantic_diff)
    return {
        "hydrated": hydrated,
        "contract_index": {
            "available": bool(contract_index),
            "version": contract_index.get("version"),
            "status": contract_index.get("status"),
            "runtime_contract_sync": (contract_index.get("summary") or {}).get("runtime_contract_sync"),
            "gap": openapi_to_ci.get("gap"),
        },
        "openapi_validation": {
            "available": bool(openapi_validation),
            "status": validation_status,
            "valid": (openapi_validation.get("summary") or {}).get("valid"),
            "error_count": len(openapi_validation.get("errors") or []),
        },
        "semantic_diff": {
            "available": bool(semantic_diff),
            "status": semantic_diff.get("status"),
            "drift_count": semantic_drift_count,
            "missing_in_backend": (semantic_diff.get("summary") or {}).get("missing_in_backend", 0),
            "missing_in_openapi": (semantic_diff.get("summary") or {}).get("missing_in_openapi", 0),
        },
        "summary": {
            "artifacts_available": sum(
                1
                for item in (
                    contract_index,
                    openapi_validation,
                    semantic_diff,
                )
                if item
            ),
            "semantic_drift_count": semantic_drift_count,
            "validation_passed": validation_status == "passed",
            "sync_gap": openapi_to_ci.get("gap"),
        },
    }


def build_correlation_chain(
    runs: list[dict[str, Any]],
    history: list[dict[str, Any]],
    coordenador: dict[str, Any],
    multi_env: dict[str, Any],
    workflow_run_id: str | None,
    commit_sha: str,
    correlation_id: str,
    contract_artifacts: dict[str, Any] | None = None,
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

    if contract_artifacts and contract_artifacts.get("hydrated"):
        summary = contract_artifacts.get("summary") or {}
        chain.append(
            {
                "sequence": seq,
                "event": "contract_artifacts_hydrated",
                "source": "contract-governance-artifacts",
                "correlation_level": "contract",
                "artifacts_available": summary.get("artifacts_available", 0),
                "semantic_drift_count": summary.get("semantic_drift_count", 0),
                "validation_passed": summary.get("validation_passed"),
                "sync_gap": summary.get("sync_gap"),
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
    contract_artifacts: dict[str, Any] | None = None,
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

    contract_summary = (contract_artifacts or {}).get("summary") or {}
    if contract_summary.get("semantic_drift_count", 0) > 0 and risk == "low":
        status, risk = "watch", "medium"

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
            "contract_artifacts_hydrated": bool((contract_artifacts or {}).get("hydrated")),
            "openapi_validation_available": bool((contract_artifacts or {}).get("openapi_validation", {}).get("available")),
            "semantic_diff_available": bool((contract_artifacts or {}).get("semantic_diff", {}).get("available")),
        },
        "sources": {
            "multi_environment": multi_env.get("summary"),
            "environment_drift": {"drift_level": drift.get("drift_level"), "findings": len(drift.get("findings") or [])},
            "slo_evidence": slo.get("summary"),
            "longitudinal": {"windows": longitudinal.get("windows"), "trend": longitudinal.get("trend")},
            "history_index": history_index.get("summary"),
            "contract_governance": contract_artifacts or {"hydrated": False},
        },
        "governed_alert": alert,
        "correlation_chain": correlation_chain,
        "recommended_actions": _recommended_actions(drift, slo, longitudinal, alert, contract_artifacts),
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
    contract_artifacts: dict[str, Any] | None = None,
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
    if contract_artifacts and contract_artifacts.get("hydrated"):
        semantic = contract_artifacts.get("semantic_diff") or {}
        if semantic.get("drift_count", 0) > 0:
            actions.append(
                f"Revisar drift semântico OpenAPI: {semantic['drift_count']} divergências "
                f"(missing_in_backend={semantic.get('missing_in_backend', 0)}, "
                f"missing_in_openapi={semantic.get('missing_in_openapi', 0)})"
            )
        sync_gap = (contract_artifacts.get("summary") or {}).get("sync_gap")
        if sync_gap:
            actions.append(f"Tratar gap de sincronização contrato: {sync_gap}")
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
    parser.add_argument(
        "--contract-artifacts-index",
        default="docs/ops-dashboard/data/contract-artifacts-index-v0.3.0.json",
    )
    parser.add_argument(
        "--openapi-validation-json",
        default="artifacts/openapi/openapi-contract-validation.json",
    )
    parser.add_argument(
        "--openapi-semantic-diff-json",
        default="artifacts/openapi/openapi-semantic-diff.json",
    )
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
    contract_artifacts = load_contract_artifacts(
        Path(args.contract_artifacts_index),
        Path(args.openapi_validation_json),
        Path(args.openapi_semantic_diff_json),
    )

    correlation_chain = build_correlation_chain(
        runs,
        history,
        coordenador,
        multi_env,
        args.workflow_run_id or None,
        args.commit_sha,
        correlation_id,
        contract_artifacts,
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
        contract_artifacts,
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
