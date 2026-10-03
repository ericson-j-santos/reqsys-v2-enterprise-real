#!/usr/bin/env python3
"""ReqSys Operational Intelligence Hub.

Consolidates outputs from:
- ReqSys Operational Health
- Operational CI Intelligence
- Failure Pattern Engine
- Actions Deep Diagnostic

The hub is read-only and only emits auditable JSON/Markdown evidence.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_LIMITS = [
    "Relatorio consolidado depende dos artifacts/arquivos de entrada disponiveis.",
    "Ausencia de evidencia em uma camada nao significa ausencia de problema.",
    "Nenhuma remediacao, rerun, merge ou deploy e executado por este hub.",
]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"available": False, "path": str(path)}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data["available"] = True
            data["path"] = str(path)
            return data
        return {"available": True, "path": str(path), "data": data}
    except Exception as exc:  # noqa: BLE001 - report evidence parsing failures without crashing silently
        return {"available": False, "path": str(path), "error": str(exc)}


def numeric(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def status_weight(status: str) -> int:
    normalized = str(status or "").upper()
    if normalized in {"VERDE", "PASSED", "PASS", "SUCCESS"}:
        return 100
    if normalized in {"AMARELO", "PENDING", "WARNING"}:
        return 70
    if normalized in {"VERMELHO", "FAILED", "FAILURE", "ERROR"}:
        return 35
    return 55


def calculate_hub_score(health: dict[str, Any], ci: dict[str, Any], fpe: dict[str, Any], diagnostic: dict[str, Any]) -> dict[str, Any]:
    components: list[dict[str, Any]] = []

    if health.get("available"):
        value = numeric(health.get("operational_health", {}).get("score_percent"), status_weight(health.get("status")))
        components.append({"name": "operational_health", "score": value, "weight": 0.35})

    if ci.get("available"):
        value = numeric(ci.get("operational_score"), status_weight(ci.get("status")))
        components.append({"name": "operational_ci_intelligence", "score": value, "weight": 0.35})

    if fpe.get("available"):
        fpe_risk = numeric(fpe.get("summary", {}).get("risk", {}).get("score"), 0)
        components.append({"name": "failure_pattern_engine", "score": max(0, 100 - fpe_risk), "weight": 0.2})

    if diagnostic.get("available"):
        failed_jobs = sum(1 for job in diagnostic.get("jobs", []) if str(job.get("conclusion")).lower() == "failure")
        components.append({"name": "actions_deep_diagnostic", "score": max(0, 100 - failed_jobs * 25), "weight": 0.1})

    if not components:
        return {"score": 0, "status": "SEM_DADOS", "components": [], "confidence": "baixa"}

    total_weight = sum(item["weight"] for item in components)
    score = round(sum(item["score"] * item["weight"] for item in components) / total_weight, 2)
    if score >= 85:
        status = "VERDE"
    elif score >= 65:
        status = "AMARELO"
    else:
        status = "VERMELHO"

    confidence = "alta" if len(components) >= 3 else "media" if len(components) == 2 else "baixa"
    return {"score": score, "status": status, "components": components, "confidence": confidence}


def extract_recommendations(*reports: dict[str, Any]) -> list[str]:
    recommendations: list[str] = []
    for report in reports:
        for key in ["recommended_next_actions", "recommended_actions"]:
            value = report.get(key)
            if isinstance(value, list):
                recommendations.extend(str(item) for item in value)
        if report.get("recommended_next_action"):
            recommendations.append(str(report["recommended_next_action"]))
    deduped: list[str] = []
    for item in recommendations:
        if item not in deduped:
            deduped.append(item)
    return deduped or ["Executar coleta completa das camadas operacionais antes de decidir nova remediacao."]


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    health = load_json(args.operational_health)
    ci = load_json(args.operational_ci)
    fpe = load_json(args.failure_patterns)
    diagnostic = load_json(args.deep_diagnostic)
    score = calculate_hub_score(health, ci, fpe, diagnostic)

    available_layers = [
        name
        for name, report in {
            "operational_health": health,
            "operational_ci_intelligence": ci,
            "failure_pattern_engine": fpe,
            "actions_deep_diagnostic": diagnostic,
        }.items()
        if report.get("available")
    ]

    return {
        "schema_version": "1.0.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "hub_score": score,
        "available_layers": available_layers,
        "missing_layers": [
            name
            for name in [
                "operational_health",
                "operational_ci_intelligence",
                "failure_pattern_engine",
                "actions_deep_diagnostic",
            ]
            if name not in available_layers
        ],
        "source_reports": {
            "operational_health": summarize_report(health),
            "operational_ci_intelligence": summarize_report(ci),
            "failure_pattern_engine": summarize_report(fpe),
            "actions_deep_diagnostic": summarize_report(diagnostic),
        },
        "recommendations": extract_recommendations(health, ci, fpe, diagnostic),
        "blocked_actions": [
            "auto_merge",
            "auto_fix_in_production",
            "unrestricted_rerun",
            "bypass_ci",
            "hide_failure_with_continue_on_error",
        ],
        "limits": DEFAULT_LIMITS,
    }


def summarize_report(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "available": bool(report.get("available")),
        "path": report.get("path"),
        "status": report.get("status") or report.get("operational_health", {}).get("status") or report.get("summary", {}).get("risk", {}).get("status"),
        "score": report.get("operational_score") or report.get("operational_health", {}).get("score_percent") or report.get("summary", {}).get("risk", {}).get("score"),
        "error": report.get("error"),
    }


def render_markdown(report: dict[str, Any]) -> str:
    hub = report["hub_score"]
    lines = [
        "# ReqSys Operational Intelligence Hub",
        "",
        f"Atualizado em UTC: `{report['generated_at_utc']}`",
        "",
        "## Semáforo consolidado",
        "",
        f"**Status:** {hub['status']}",
        f"**Score:** {hub['score']}%",
        f"**Confiança:** {hub['confidence']}",
        "",
        "## Camadas",
        "",
        "| Camada | Disponível | Status | Score | Fonte |",
        "|---|---:|---|---:|---|",
    ]
    for name, summary in report["source_reports"].items():
        lines.append(
            f"| {name} | {summary['available']} | {summary.get('status') or '-'} | {summary.get('score') or '-'} | `{summary.get('path')}` |"
        )

    lines.extend(["", "## Componentes do score", "", "| Componente | Score | Peso |", "|---|---:|---:|"])
    for component in hub.get("components", []):
        lines.append(f"| {component['name']} | {component['score']} | {component['weight']} |")

    lines.extend(["", "## Recomendações", ""])
    lines.extend(f"- {item}" for item in report["recommendations"])
    lines.extend(["", "## Ações bloqueadas", ""])
    lines.extend(f"- `{item}`" for item in report["blocked_actions"])
    lines.extend(["", "## Limites", ""])
    lines.extend(f"- {item}" for item in report["limits"])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build consolidated ReqSys Operational Intelligence Hub report.")
    parser.add_argument("--operational-health", type=Path, default=Path("artifacts/operational-health/operational-health.json"))
    parser.add_argument("--operational-ci", type=Path, default=Path("artifacts/operational-ci-intelligence/operational-ci-intelligence.json"))
    parser.add_argument("--failure-patterns", type=Path, default=Path("artifacts/failure-pattern-engine/failure-pattern-report.json"))
    parser.add_argument("--deep-diagnostic", type=Path, default=Path("artifacts/deep-diagnostic/deep-diagnostic.json"))
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/operational-intelligence-hub"))
    args = parser.parse_args()

    report = build_report(args)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "operational-intelligence-hub.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.out_dir / "operational-intelligence-hub.md").write_text(render_markdown(report), encoding="utf-8")
    print(render_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
