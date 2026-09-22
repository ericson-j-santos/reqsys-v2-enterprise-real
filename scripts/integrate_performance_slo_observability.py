#!/usr/bin/env python3
"""Integra Performance SLO/Error Budget ao Operational Observability Hub e Ops Dashboard.

Report-only: evidencia ausente/obsoleta nunca e convertida em estado saudavel.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"
CHECK_ID = "performance_slo_error_budget"
MARKER_START = "<!-- performance-slo-observability:start -->"
MARKER_END = "<!-- performance-slo-observability:end -->"


def _load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON deve ser objeto: {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _age_hours(generated_at: str | None, now: datetime) -> float | None:
    generated = _parse_iso(generated_at)
    if generated is None:
        return None
    return round(max(0.0, (now - generated).total_seconds() / 3600.0), 2)


def _source_run_from_correlation(correlation_id: str | None) -> str | None:
    match = re.fullmatch(r"performance-slo-(\d+)", str(correlation_id or ""))
    return match.group(1) if match else None


def _alert(level: str, alert_type: str, action_policy: str, message: str, should_alert: bool = True) -> dict[str, Any]:
    return {
        "alert_level": level,
        "alert_type": alert_type,
        "action_policy": action_policy,
        "should_alert": should_alert,
        "source": "performance_slo_error_budget",
        "message": message,
        "mode": "governed_report_only",
    }


def normalize_performance_slo(
    report: dict[str, Any],
    provenance: dict[str, Any],
    *,
    now: datetime | None = None,
    max_age_hours: float = 36.0,
) -> dict[str, Any]:
    now = (now or datetime.now(UTC)).astimezone(UTC)
    provenance_state = str(provenance.get("state") or "").lower()
    conclusion = str(provenance.get("source_workflow_conclusion") or "").lower()
    artifact_expected = bool(provenance.get("artifact_expected"))
    artifact_found = bool(provenance.get("artifact_found"))

    if provenance_state == "not_applicable":
        return {
            "schema_version": SCHEMA_VERSION,
            "source": "performance-slo-error-budget",
            "available": False,
            "current": False,
            "state": "not_applicable",
            "status": "not_applicable",
            "operational_risk": "low",
            "generated_at": None,
            "age_hours": None,
            "summary": {},
            "slos": [],
            "error_budget": {"worst_remaining_percent": None},
            "trend": {"direction": "not_applicable", "sustained_status": "not_applicable", "point_regressions_total": 0},
            "alert": _alert("INFO", "PERFORMANCE_SLO_NOT_APPLICABLE", "OBSERVE", "Sem medicao live elegivel; nenhum SLO foi calculado.", False),
            "provenance": provenance,
        }

    if not report:
        hard_missing = provenance_state in {"artifact_missing", "source_failed"} or artifact_expected or conclusion == "failure"
        state = "artifact_missing" if artifact_expected and not artifact_found else ("source_failed" if hard_missing else "unavailable")
        return {
            "schema_version": SCHEMA_VERSION,
            "source": "performance-slo-error-budget",
            "available": False,
            "current": False,
            "state": state,
            "status": "unknown",
            "operational_risk": "high" if hard_missing else "low",
            "generated_at": None,
            "age_hours": None,
            "summary": {},
            "slos": [],
            "error_budget": {"worst_remaining_percent": None},
            "trend": {"direction": "unknown", "sustained_status": "unknown", "point_regressions_total": 0},
            "alert": _alert(
                "HIGH" if hard_missing else "INFO",
                "PERFORMANCE_SLO_EVIDENCE_MISSING" if hard_missing else "PERFORMANCE_SLO_UNAVAILABLE",
                "MANUAL_REVIEW_REQUIRED" if hard_missing else "OBSERVE",
                "Artifact SLO esperado esta ausente; nao reutilizar evidencia anterior." if hard_missing else "Evidencia de performance ainda nao disponivel.",
                hard_missing,
            ),
            "provenance": provenance,
        }

    generated_at = report.get("generated_at")
    age = _age_hours(str(generated_at or ""), now)
    stale = age is None or age > max_age_hours
    raw_status = str(report.get("status") or "unknown")
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    raw_slos = report.get("slos") if isinstance(report.get("slos"), list) else []
    slos: list[dict[str, Any]] = []
    remaining: list[float] = []
    for item in raw_slos:
        if not isinstance(item, dict):
            continue
        value = item.get("error_budget_remaining_percent")
        if isinstance(value, (int, float)):
            remaining.append(float(value))
        slos.append({
            "slo_id": item.get("slo_id"),
            "name": item.get("name"),
            "status": item.get("status"),
            "mature": item.get("mature"),
            "actual_percent": item.get("actual_percent"),
            "target_percent": item.get("target_percent"),
            "error_budget_remaining_percent": value,
            "eligible_measurements": item.get("eligible_measurements"),
            "bad_measurements": item.get("bad_measurements"),
        })

    sustained = report.get("sustained_degradation") if isinstance(report.get("sustained_degradation"), dict) else {}
    sustained_status = str(sustained.get("status") or "unknown")
    point_regressions = int(summary.get("point_regressions_total") or 0)
    direction = "worsening" if sustained_status == "degraded" else ("point_regression" if point_regressions > 0 else ("stable" if sustained_status == "stable" else "insufficient_history"))

    if stale:
        state, risk = "stale", "medium"
        alert = _alert("MEDIUM", "PERFORMANCE_SLO_EVIDENCE_STALE", "REFRESH_EVIDENCE", f"Evidencia SLO esta obsoleta ({age}h).")
    elif raw_status == "blocked":
        state, risk = "blocked", "high"
        alert = _alert("HIGH", "PERFORMANCE_SLO_BREACH", "MANUAL_REVIEW_REQUIRED", "SLO de performance bloqueado por breach/error budget ou degradacao sustentada.")
    elif raw_status == "watch":
        state, risk = "watch", "medium"
        alert = _alert("MEDIUM", "PERFORMANCE_SLO_WATCH", "VERIFY_CONTEXT", "Performance em observacao: error budget baixo ou regressao pontual.")
    elif raw_status == "passed":
        state, risk = "healthy", "low"
        alert = _alert("INFO", "PERFORMANCE_SLO_HEALTHY", "OBSERVE", "SLO de performance dentro da politica.", False)
    elif raw_status == "insufficient_history":
        state, risk = "insufficient_history", "low"
        alert = _alert("INFO", "PERFORMANCE_SLO_INSUFFICIENT_HISTORY", "COLLECT_MORE_SAMPLES", "Historico ainda insuficiente para decisao madura.", False)
    else:
        state, risk = "unknown", "medium"
        alert = _alert("MEDIUM", "PERFORMANCE_SLO_UNKNOWN", "VERIFY_CONTEXT", f"Status SLO inesperado: {raw_status}.")

    correlation_id = report.get("correlation_id")
    return {
        "schema_version": SCHEMA_VERSION,
        "source": "performance-slo-error-budget",
        "available": True,
        "current": not stale,
        "state": state,
        "status": raw_status,
        "operational_risk": risk,
        "generated_at": generated_at,
        "age_hours": age,
        "max_age_hours": max_age_hours,
        "environment": report.get("environment"),
        "correlation_id": correlation_id,
        "dynamic_performance_run_id": _source_run_from_correlation(str(correlation_id or "")),
        "summary": summary,
        "slos": slos,
        "error_budget": {
            "worst_remaining_percent": round(min(remaining), 2) if remaining else None,
            "warning_count": int(summary.get("warning_count") or 0),
            "breach_count": int(summary.get("breach_count") or 0),
        },
        "trend": {
            "direction": direction,
            "sustained_status": sustained_status,
            "sustained_degradations_total": int(summary.get("sustained_degradations_total") or 0),
            "required_consecutive": sustained.get("required_consecutive"),
            "point_regressions_total": point_regressions,
        },
        "alert": alert,
        "provenance": provenance,
    }


def _risk_rank(value: str | None) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(str(value or "").lower(), 0)


def _alert_rank(value: str | None) -> int:
    return {"INFO": 0, "MEDIUM": 1, "HIGH": 2}.get(str(value or "").upper(), 0)


def _recommended_action(normalized: dict[str, Any]) -> str | None:
    state = normalized.get("state")
    if state == "blocked":
        return "Performance SLO: tratar breach/error budget ou degradacao sustentada antes de promover mudancas de risco."
    if state == "watch":
        return "Performance SLO: revisar regressoes pontuais e error budget antes que o orcamento seja esgotado."
    if state == "stale":
        return "Performance SLO: renovar evidencia live; dados obsoletos nao podem sustentar decisao operacional."
    if state in {"artifact_missing", "source_failed"}:
        return "Performance SLO: corrigir cadeia de evidencia; artifact esperado esta ausente ou o workflow fonte falhou."
    if state == "insufficient_history":
        return "Performance SLO: coletar mais amostras para maturar a janela estatistica."
    return None


def inject_hub(hub: dict[str, Any], normalized: dict[str, Any]) -> dict[str, Any]:
    if not hub:
        return hub
    hub.setdefault("sources", {})["performance_slo"] = normalized
    pareto = hub.setdefault("pareto_increment", {})
    pareto["performance_slo_error_budget"] = bool(normalized.get("available"))
    pareto["performance_slo_current"] = bool(normalized.get("current"))

    chain = [item for item in (hub.get("correlation_chain") or []) if item.get("event") != "performance_slo_evidence"]
    if normalized.get("state") != "unavailable":
        chain.append({
            "sequence": len(chain) + 1,
            "event": "performance_slo_evidence",
            "source": "performance-slo-error-budget",
            "correlation_level": "performance",
            "status": normalized.get("status"),
            "state": normalized.get("state"),
            "source_workflow_run_id": (normalized.get("provenance") or {}).get("source_workflow_run_id"),
            "dynamic_performance_run_id": normalized.get("dynamic_performance_run_id"),
            "error_budget_remaining_percent": (normalized.get("error_budget") or {}).get("worst_remaining_percent"),
            "trend": (normalized.get("trend") or {}).get("direction"),
            "correlation_id": normalized.get("correlation_id") or hub.get("correlation_id"),
        })
    hub["correlation_chain"] = chain

    perf_risk = str(normalized.get("operational_risk") or "low")
    if _risk_rank(perf_risk) > _risk_rank(str(hub.get("operational_risk") or "low")):
        hub["operational_risk"] = perf_risk
        hub["status"] = "degraded" if perf_risk == "high" else "watch"

    perf_alert = normalized.get("alert") or {}
    alerts = [item for item in (hub.get("governed_alerts") or []) if item.get("source") != "performance_slo_error_budget"]
    if perf_alert.get("should_alert"):
        alerts.append(perf_alert)
    hub["governed_alerts"] = alerts
    current_alert = hub.get("governed_alert") if isinstance(hub.get("governed_alert"), dict) else {}
    if perf_alert.get("should_alert") and _alert_rank(perf_alert.get("alert_level")) > _alert_rank(current_alert.get("alert_level")):
        hub["governed_alert"] = perf_alert

    actions = [item for item in (hub.get("recommended_actions") or []) if not str(item).startswith("Performance SLO:")]
    recommendation = _recommended_action(normalized)
    if recommendation:
        actions.insert(0, recommendation)
    hub["recommended_actions"] = actions[:10]
    return hub


def combine_slo_evidence(existing: dict[str, Any], normalized: dict[str, Any], now: datetime) -> dict[str, Any]:
    operational = existing.get("operational") if existing.get("source") == "operational-observability-hub-slo-consolidation" else existing
    operational = operational if isinstance(operational, dict) else {}
    return {
        "schema_version": "2.0.0",
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "source": "operational-observability-hub-slo-consolidation",
        "operational": operational,
        "performance": normalized,
        "summary": {
            "operational_available": bool(operational),
            "performance_available": bool(normalized.get("available")),
            "performance_current": bool(normalized.get("current")),
            "performance_status": normalized.get("status"),
            "performance_state": normalized.get("state"),
            "performance_error_budget_remaining_percent": (normalized.get("error_budget") or {}).get("worst_remaining_percent"),
            "performance_trend": (normalized.get("trend") or {}).get("direction"),
            "performance_alert": (normalized.get("alert") or {}).get("alert_type"),
        },
    }


def _dashboard_status(normalized: dict[str, Any]) -> tuple[str, str]:
    state = normalized.get("state")
    if state in {"blocked", "artifact_missing", "source_failed"}:
        return "failed", "critical"
    if state in {"watch", "stale", "unknown"}:
        return "warning", "warning"
    if state == "healthy":
        return "passed", "normal"
    return "unknown", "info"


def inject_dashboard_health(health: dict[str, Any], normalized: dict[str, Any], combined_slo: dict[str, Any]) -> dict[str, Any]:
    health = health or {}
    health["performance_slo"] = normalized
    health["slo_evidence"] = combined_slo
    runtime_sources = health.setdefault("runtime_sources", {})
    runtime_sources["performance_slo_evidence_available"] = bool(normalized.get("available"))
    runtime_sources["performance_slo_evidence_current"] = bool(normalized.get("current"))

    status, severity = _dashboard_status(normalized)
    recommendation = _recommended_action(normalized) or (normalized.get("alert") or {}).get("message") or "Continuar monitoramento."
    check = {
        "id": CHECK_ID,
        "name": "Performance SLO / Error Budget",
        "domain": "performance",
        "status": status,
        "severity": severity,
        "recommendation": recommendation,
        "evidence": {
            "state": normalized.get("state"),
            "slo_status": normalized.get("status"),
            "current": normalized.get("current"),
            "generated_at": normalized.get("generated_at"),
            "age_hours": normalized.get("age_hours"),
            "source_workflow_run_id": (normalized.get("provenance") or {}).get("source_workflow_run_id"),
            "source_url": (normalized.get("provenance") or {}).get("source_url"),
            "dynamic_performance_run_id": normalized.get("dynamic_performance_run_id"),
            "error_budget_remaining_percent": (normalized.get("error_budget") or {}).get("worst_remaining_percent"),
            "trend": normalized.get("trend"),
            "summary": normalized.get("summary"),
            "slos": normalized.get("slos"),
            "alert": normalized.get("alert"),
        },
    }
    checks = [item for item in (health.get("checks") or []) if item.get("id") != CHECK_ID and item.get("name") != "Performance SLO / Error Budget"]
    checks.append(check)
    health["checks"] = checks

    timeline = [item for item in (health.get("incident_timeline") or []) if item.get("source") != "performance_slo_error_budget"]
    if normalized.get("state") != "unavailable":
        timeline.append({
            "source": "performance_slo_error_budget",
            "title": "Performance SLO / Error Budget",
            "domain": "performance",
            "workflow": "Performance SLO Error Budget Gate",
            "pr": "",
            "status": status,
            "severity": severity,
            "evidence": check["evidence"],
        })
    health["incident_timeline"] = timeline
    return health


def render_markdown_section(normalized: dict[str, Any]) -> str:
    budget = (normalized.get("error_budget") or {}).get("worst_remaining_percent")
    budget_text = "—" if budget is None else f"{budget:.2f}%"
    trend = (normalized.get("trend") or {}).get("direction") or "unknown"
    alert = normalized.get("alert") or {}
    provenance = normalized.get("provenance") or {}
    run_id = provenance.get("source_workflow_run_id") or "—"
    source_url = provenance.get("source_url") or ""
    run_text = f"[{run_id}]({source_url})" if source_url else f"`{run_id}`"
    lines = [
        MARKER_START,
        "## Performance SLO / Error Budget",
        "",
        f"- Estado: `{normalized.get('state')}`",
        f"- SLO: `{normalized.get('status')}`",
        f"- Error budget restante (pior SLO): `{budget_text}`",
        f"- Tendencia: `{trend}`",
        f"- Alerta: `{alert.get('alert_level', 'INFO')} / {alert.get('alert_type', 'n/a')}`",
        f"- Run fonte: {run_text}",
        f"- Evidencia atual: `{bool(normalized.get('current'))}`",
        "",
        "| SLO | Atual | Alvo | Budget restante | Status |",
        "|---|---:|---:|---:|---|",
    ]
    for item in normalized.get("slos") or []:
        actual = item.get("actual_percent")
        remaining = item.get("error_budget_remaining_percent")
        target = item.get("target_percent")
        actual_text = "—" if actual is None else f"{float(actual):.2f}%"
        target_text = "—" if target is None else f"{float(target):.2f}%"
        remaining_text = "—" if remaining is None else f"{float(remaining):.2f}%"
        lines.append(f"| `{item.get('slo_id')}` | {actual_text} | {target_text} | {remaining_text} | {item.get('status')} |")
    if not normalized.get("slos"):
        lines.append("| — | — | — | — | sem evidencia elegivel |")
    lines.extend(["", MARKER_END])
    return "\n".join(lines)


def inject_markdown(markdown: str, normalized: dict[str, Any]) -> str:
    section = render_markdown_section(normalized)
    pattern = re.compile(re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END), re.DOTALL)
    if pattern.search(markdown):
        return pattern.sub(section, markdown)
    return markdown.rstrip() + "\n\n" + section + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Integra Performance SLO ao Hub e Ops Dashboard.")
    parser.add_argument("--performance-slo", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    parser.add_argument("--hub-json", type=Path)
    parser.add_argument("--hub-markdown", type=Path)
    parser.add_argument("--dashboard-health", type=Path)
    parser.add_argument("--dashboard-slo", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-age-hours", type=float, default=36.0)
    parser.add_argument("--now", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        now = _parse_iso(args.now) if args.now else datetime.now(UTC)
        assert now is not None
        report = _load_json(args.performance_slo)
        provenance = _load_json(args.provenance)
        normalized = normalize_performance_slo(report, provenance, now=now, max_age_hours=args.max_age_hours)
        _write_json(args.output, normalized)

        hub = _load_json(args.hub_json)
        if args.hub_json and hub:
            _write_json(args.hub_json, inject_hub(hub, normalized))
        if args.hub_markdown and args.hub_markdown.exists():
            current = args.hub_markdown.read_text(encoding="utf-8")
            args.hub_markdown.write_text(inject_markdown(current, normalized), encoding="utf-8")

        existing_slo = _load_json(args.dashboard_slo)
        combined = combine_slo_evidence(existing_slo, normalized, now)
        if args.dashboard_slo:
            _write_json(args.dashboard_slo, combined)
        if args.dashboard_health:
            health = _load_json(args.dashboard_health)
            _write_json(args.dashboard_health, inject_dashboard_health(health, normalized, combined))
        return 0
    except Exception as exc:
        print(f"performance_slo_observability_error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
