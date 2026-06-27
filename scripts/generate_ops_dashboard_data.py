#!/usr/bin/env python3
"""Generate static operations dashboard data.

Entrada principal: artifact/relatorio do Repository Health Watchdog.
Saida: JSON estatico consumido por docs/ops-dashboard/index.html.

Este script e deterministico e nao acessa rede.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any


def _load_watchdog_report(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "overall_status": "unknown",
            "critical_failure_count": None,
            "warning_count": None,
            "results": [],
            "source_missing": True,
        }
    return json.loads(path.read_text(encoding="utf-8"))


def _score(report: dict[str, Any]) -> int:
    status = report.get("overall_status")
    critical = int(report.get("critical_failure_count") or 0)
    warnings = int(report.get("warning_count") or 0)
    if status == "passed":
        return 100
    if status == "warning":
        return max(60, 90 - warnings * 10)
    if status == "failed":
        return max(0, 50 - critical * 25 - warnings * 5)
    return 40


def _load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_number(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            normalized = value.strip().replace("%", "").replace(",", ".")
            try:
                return float(normalized)
            except ValueError:
                continue
    return None


def _delivery_finalization_summary(delivery_report: dict[str, Any]) -> dict[str, Any]:
    score = _safe_number(
        delivery_report.get("final_score"),
        delivery_report.get("score_final"),
        delivery_report.get("score"),
        delivery_report.get("completion_score"),
        delivery_report.get("summary", {}).get("final_score") if isinstance(delivery_report.get("summary"), dict) else None,
    )
    residual_gap = _safe_number(
        delivery_report.get("residual_gap"),
        delivery_report.get("gap_residual"),
        delivery_report.get("gap"),
        delivery_report.get("summary", {}).get("residual_gap") if isinstance(delivery_report.get("summary"), dict) else None,
    )
    raw_indicators = delivery_report.get("indicators") or delivery_report.get("indicadores") or []
    indicators = raw_indicators if isinstance(raw_indicators, list) else []
    normalized_indicators = [
        {
            "id": item.get("id") or item.get("name") or item.get("nome") or f"indicator-{index + 1}",
            "name": item.get("name") or item.get("nome") or item.get("id") or f"Indicador {index + 1}",
            "status": item.get("status", "unknown"),
            "score": _safe_number(item.get("score"), item.get("value"), item.get("valor")),
            "gap": _safe_number(item.get("gap"), item.get("residual_gap"), item.get("gap_residual")),
            "evidence": item.get("evidence") or item.get("evidencia") or item.get("evidências") or {},
        }
        for index, item in enumerate(indicators)
        if isinstance(item, dict)
    ]
    status = (
        delivery_report.get("status")
        or delivery_report.get("overall_status")
        or delivery_report.get("final_status")
        or ("unknown" if not delivery_report else "available")
    )
    return {
        "available": bool(delivery_report),
        "artifact": "delivery-finalization-report.json",
        "status": status,
        "final_score": score,
        "residual_gap": residual_gap,
        "indicator_count": len(normalized_indicators),
        "passed_indicator_count": sum(1 for item in normalized_indicators if str(item.get("status")).lower() in {"passed", "ok", "success", "healthy"}),
        "indicators": normalized_indicators,
        "guardrail": "Fallback seguro: nenhum dado externo é consultado quando o artifact não existe.",
    }


def _runtime_depth(runtime_report: dict[str, Any]) -> dict[str, Any]:
    depth = runtime_report.get("gold_standard_depth") or {}
    axes = depth.get("axes") or {}
    return {
        "available": bool(depth),
        "strategy": depth.get("strategy", ""),
        "overall_status": depth.get("overall_status", "unknown"),
        "overall_score": depth.get("overall_score"),
        "focus_order": depth.get("operational_focus_order", []),
        "axes": [
            {
                "id": axis_id,
                "status": axis.get("status"),
                "score": axis.get("score"),
                "operator_action": axis.get("operator_action"),
            }
            for axis_id, axis in axes.items()
        ],
    }


def _severity_from_status(status: Any) -> str:
    normalized = str(status or "unknown").lower()
    if normalized in {"failed", "failure", "critical", "unhealthy", "high"}:
        return "critical"
    if normalized in {"warning", "warn", "medium", "degraded"}:
        return "warning"
    if normalized in {"partial", "pending", "unknown", "missing"}:
        return "info"
    return "normal"


def _domain_drilldowns(runtime_report: dict[str, Any]) -> list[dict[str, Any]]:
    domains = runtime_report.get("domains") or {}
    environment_drift = runtime_report.get("environment_drift") or {}
    risk = runtime_report.get("runtime_risk_scoring") or {}
    rows: list[dict[str, Any]] = []
    for domain_id, domain in domains.items():
        signals = domain.get("signals") or []
        domain_findings = environment_drift.get("findings") if domain_id == "environment" else []
        rows.append({
            "id": domain_id,
            "status": domain.get("status", "unknown"),
            "severity": _severity_from_status(domain.get("status")),
            "score": domain.get("score"),
            "signals_available": domain.get("signals_available", 0),
            "signals_total": domain.get("signals_total", 0),
            "health": {
                "maturity_percent": runtime_report.get("maturity_percent"),
                "confidence_level": runtime_report.get("confidence_level"),
                "operational_risk": runtime_report.get("operational_risk"),
            },
            "evidence": [signal for signal in signals if signal.get("available")],
            "missing_evidence": [signal for signal in signals if not signal.get("available")],
            "risk": risk if domain_id == "runtime_risk" else {"status": domain.get("status"), "severity": _severity_from_status(domain.get("status"))},
            "environment_drift": environment_drift if domain_id == "environment" else {"findings": domain_findings},
            "governance": {
                "guardrails": runtime_report.get("guardrails", []),
                "next_required_actions": runtime_report.get("next_required_actions", []),
                "gold_standard_status": runtime_report.get("gold_standard_status", {}),
            } if domain_id == "governance" else {},
        })
    return rows


def _extract_pr(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    match = re.search(r"#(\d+)|pull/(\d+)|PR[-_ ]?(\d+)", text, re.IGNORECASE)
    if not match:
        return ""
    return next(group for group in match.groups() if group)


def _incident_timeline(report: dict[str, Any], runtime_report: dict[str, Any], evidence_graph: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for check in report.get("results", []) or []:
        events.append({
            "source": "repository_health_watchdog",
            "title": check.get("name", "check operacional"),
            "domain": check.get("domain") or check.get("category") or "ci_cd",
            "workflow": check.get("workflow") or check.get("name", ""),
            "pr": _extract_pr(check),
            "status": check.get("status", "unknown"),
            "severity": check.get("severity") or _severity_from_status(check.get("status")),
            "evidence": check.get("evidence", {}),
        })
    for domain_id, domain in (runtime_report.get("domains") or {}).items():
        events.append({
            "source": "runtime_health_report",
            "title": f"Domínio {domain_id}",
            "domain": domain_id,
            "workflow": "runtime-health-center",
            "pr": "",
            "status": domain.get("status", "unknown"),
            "severity": _severity_from_status(domain.get("status")),
            "evidence": {"score": domain.get("score"), "signals_available": domain.get("signals_available"), "signals_total": domain.get("signals_total")},
        })
    for artifact in ((runtime_report.get("ingested_artifacts") or {}).get("artifacts") or []):
        events.append({
            "source": "runtime_artifact_catalog",
            "title": artifact.get("id", "artifact"),
            "domain": "evidence_gate",
            "workflow": artifact.get("id", ""),
            "pr": _extract_pr(artifact),
            "status": artifact.get("status", "unknown"),
            "severity": _severity_from_status(artifact.get("status")),
            "evidence": artifact,
        })
    graph_items = []
    for key in ("events", "nodes", "edges"):
        value = evidence_graph.get(key)
        if isinstance(value, list):
            graph_items.extend(value)
    for item in graph_items:
        if not isinstance(item, dict):
            continue
        events.append({
            "source": "runtime_operational_evidence_graph",
            "title": item.get("title") or item.get("id") or item.get("name") or "evidência correlacionada",
            "domain": item.get("domain") or item.get("type") or "evidence_gate",
            "workflow": item.get("workflow") or item.get("workflow_name") or "",
            "pr": str(item.get("pr") or item.get("pull_request") or _extract_pr(item)),
            "status": item.get("status", "unknown"),
            "severity": item.get("severity") or _severity_from_status(item.get("status")),
            "evidence": item,
        })
    return events


def _public_runtime_summary(public_runtime: dict[str, Any]) -> dict[str, Any]:
    readiness = public_runtime.get("readiness") or {}
    return {
        "available": bool(public_runtime),
        "environment": readiness.get("environment") or public_runtime.get("environment") or "prod",
        "base_url": public_runtime.get("base_url", ""),
        "operational_status": readiness.get("operational_status", "unknown"),
        "readiness_percent": readiness.get("readiness_percent"),
        "response_time": readiness.get("response_time"),
        "dashboard_ready": readiness.get("dashboard_ready", False),
        "login_ready": readiness.get("login_ready", False),
        "api_ready": readiness.get("api_ready", False),
        "runtime_ready": readiness.get("runtime_ready", False),
        "evidence_ready": readiness.get("evidence_ready", False),
        "blocking_issues": readiness.get("blocking_issues", []),
        "checks": public_runtime.get("checks", {}),
    }


def build_dashboard_payload(
    report: dict[str, Any],
    repo: str,
    runtime_report: dict[str, Any] | None = None,
    evidence_graph: dict[str, Any] | None = None,
    public_runtime: dict[str, Any] | None = None,
    observability_correlation: dict[str, Any] | None = None,
    delivery_finalization: dict[str, Any] | None = None,
) -> dict[str, Any]:
    results = report.get("results", []) or []
    runtime_report = runtime_report or {}
    evidence_graph = evidence_graph or {}
    public_runtime = public_runtime or {}
    observability_correlation = observability_correlation or {}
    delivery_finalization = delivery_finalization or {}
    return {
        "schema_version": "1.2.0",
        "repo": repo or report.get("repo") or "unknown",
        "generated_at_epoch": int(time.time()),
        "overall_status": report.get("overall_status", "unknown"),
        "health_score": _score(report),
        "critical_failure_count": report.get("critical_failure_count"),
        "warning_count": report.get("warning_count"),
        "source_missing": report.get("source_missing", False),
        "checks": results,
        "links": {
            "actions": f"https://github.com/{repo}/actions" if repo else "",
            "pulls": f"https://github.com/{repo}/pulls" if repo else "",
            "main": f"https://github.com/{repo}/tree/main" if repo else "",
        },
        "public_runtime_readiness": _public_runtime_summary(public_runtime),
        "runtime_gold_standard_depth": _runtime_depth(runtime_report),
        "runtime_domain_drilldowns": _domain_drilldowns(runtime_report),
        "incident_timeline": _incident_timeline(report, runtime_report, evidence_graph),
        "observability_correlation_report": observability_correlation,
        "delivery_finalization": _delivery_finalization_summary(delivery_finalization),
        "runtime_sources": {
            "runtime_health_report_available": bool(runtime_report),
            "runtime_operational_evidence_graph_available": bool(evidence_graph),
            "public_runtime_validation_available": bool(public_runtime),
            "observability_correlation_report_available": bool(observability_correlation),
            "delivery_finalization_report_available": bool(delivery_finalization),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate ReqSys ops dashboard data")
    parser.add_argument("--watchdog-report", default="artifacts/repository-health-watchdog/repository-health-report.json")
    parser.add_argument("--repo", default="")
    parser.add_argument("--output", default="docs/ops-dashboard/data/health.json")
    parser.add_argument("--runtime-health-report", default="artifacts/runtime-health-center/runtime-health-report.json")
    parser.add_argument("--evidence-graph", default="artifacts/runtime-operational-evidence-graph/runtime-operational-evidence-graph.json")
    parser.add_argument("--public-runtime-validation", default="artifacts/runtime/public-runtime-validation.json")
    parser.add_argument("--observability-correlation-report", default="artifacts/observability-correlation-report/observability-correlation-report.json")
    parser.add_argument("--delivery-finalization-report", default="artifacts/delivery-finalization/delivery-finalization-report.json")
    args = parser.parse_args()

    report = _load_watchdog_report(Path(args.watchdog_report))
    runtime_report = _load_optional_json(Path(args.runtime_health_report))
    evidence_graph = _load_optional_json(Path(args.evidence_graph))
    public_runtime = _load_optional_json(Path(args.public_runtime_validation))
    observability_correlation = _load_optional_json(Path(args.observability_correlation_report))
    delivery_finalization = _load_optional_json(Path(args.delivery_finalization_report))
    payload = build_dashboard_payload(report, args.repo, runtime_report, evidence_graph, public_runtime, observability_correlation, delivery_finalization)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
