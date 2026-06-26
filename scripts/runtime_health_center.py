#!/usr/bin/env python3
"""ReqSys Runtime Health Center.

Local-only operational status aggregator for Runtime Ops Governance P1.
It reads existing JSON/check artifacts when present and emits a versioned
runtime-health-report.json for CI artifacts and future dashboard/API use.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATUSES = ("missing", "partial", "warning", "passed")
STATUS_SCORE = {"missing": 0, "partial": 45, "warning": 70, "passed": 100}
DOMAIN_WEIGHTS = {
    "ci_cd": 0.22,
    "living_architecture": 0.18,
    "evidence": 0.18,
    "environment": 0.14,
    "governance": 0.16,
    "remediation": 0.12,
}
DEFAULT_OUTPUT = Path("artifacts/runtime-health-center/runtime-health-report.json")


@dataclass(frozen=True)
class LocalSignal:
    id: str
    path: Path
    required: bool = False
    json_status_path: tuple[str, ...] = ()


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"_parse_error": True}
    return data if isinstance(data, dict) else {"data": data}


def nested_value(data: dict[str, Any] | None, keys: tuple[str, ...]) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def normalize_status(value: Any, exists: bool) -> str:
    if not exists:
        return "missing"
    if value is None:
        return "passed" if exists else "missing"
    normalized = str(value or "").strip().lower()
    if normalized in {"passed", "pass", "success", "successful", "healthy", "verde", "ok"}:
        return "passed"
    if normalized in {"warning", "warn", "amarelo", "degraded", "unstable"}:
        return "warning"
    if normalized in {"partial", "pending", "unknown", "sem_dados", "not_ready"}:
        return "partial"
    if normalized in {"failed", "failure", "error", "unhealthy", "vermelho", "critical"}:
        return "warning"
    return "partial"


def classify_domain(required_total: int, present_total: int, signal_statuses: list[str]) -> str:
    if present_total == 0:
        return "missing"
    if signal_statuses and all(status == "passed" for status in signal_statuses) and present_total >= required_total:
        return "passed"
    if any(status == "warning" for status in signal_statuses):
        return "warning"
    return "partial"


def evaluate_domain(name: str, signals: list[LocalSignal], root: Path) -> dict[str, Any]:
    evaluated: list[dict[str, Any]] = []
    present_total = 0
    statuses: list[str] = []
    for signal in signals:
        absolute = root / signal.path
        data = load_json(absolute) if absolute.suffix == ".json" else None
        exists = absolute.exists()
        if exists:
            present_total += 1
        raw_status = nested_value(data, signal.json_status_path) if signal.json_status_path else None
        status = normalize_status(raw_status, exists)
        statuses.append(status)
        evaluated.append(
            {
                "id": signal.id,
                "path": signal.path.as_posix(),
                "available": exists,
                "required": signal.required,
                "status": status,
                "parse_error": bool(data and data.get("_parse_error")),
            }
        )
    required_total = sum(1 for signal in signals if signal.required)
    domain_status = classify_domain(required_total, present_total, statuses)
    return {
        "status": domain_status,
        "score": STATUS_SCORE[domain_status],
        "signals_total": len(signals),
        "signals_available": present_total,
        "signals": evaluated,
    }


def signal_catalog() -> dict[str, list[LocalSignal]]:
    return {
        "ci_cd": [
            LocalSignal("enterprise_fast_ci", Path(".github/workflows/ci-enterprise-fast.yml"), True),
            LocalSignal("governed_ci_validation", Path(".github/workflows/pr-governed-ci-validation.yml"), True),
            LocalSignal("runtime_health_workflow", Path(".github/workflows/runtime-operational-health.yml")),
            LocalSignal("runtime_health_validator_report", Path("artifacts/runtime-health-validator/runtime-health-validator.json"), json_status_path=("status",)),
        ],
        "living_architecture": [
            LocalSignal("runtime_ops_governance_p1_doc", Path("docs/operations/runtime-ops-governance-p1.md"), True),
            LocalSignal("adr_directory", Path("docs/adr"), True),
            LocalSignal("runbooks_directory", Path("docs/runbooks"), True),
            LocalSignal("living_architecture_drift_artifact", Path("artifacts/living-architecture-doc-drift/living-architecture-doc-drift.json"), json_status_path=("status",)),
        ],
        "evidence": [
            LocalSignal("runtime_evidence_runbook", Path("docs/runbooks/runtime-evidence-analytics.md"), True),
            LocalSignal("public_runtime_evidence_workflow", Path(".github/workflows/public-runtime-evidence.yml"), True),
            LocalSignal("operational_intelligence_hub_artifact", Path("artifacts/operational-intelligence-hub/operational-intelligence-hub.json"), json_status_path=("hub_score", "status")),
            LocalSignal("runtime_operational_evidence_graph", Path("artifacts/runtime-operational-evidence-graph/runtime-operational-evidence-graph.json"), json_status_path=("status",)),
        ],
        "environment": [
            LocalSignal("dev_compose", Path("docker-compose.dev.yml"), True),
            LocalSignal("test_compose", Path("docker-compose.test.yml"), True),
            LocalSignal("prod_compose", Path("docker-compose.prod.yml"), True),
            LocalSignal("production_gate_tests", Path("backend/tests/test_security_production_gates.py"), True),
        ],
        "governance": [
            LocalSignal("agents_operational_rules", Path("AGENTS.md"), True),
            LocalSignal("runtime_ops_p1_doc", Path("docs/operations/runtime-ops-governance-p1.md"), True),
            LocalSignal("governance_gate_workflow", Path(".github/workflows/operational-governance-gate.yml"), True),
            LocalSignal("governance_gate_report", Path("artifacts/operational-governance-gate/operational-governance-gate.json"), json_status_path=("status",)),
        ],
        "remediation": [
            LocalSignal("runtime_remediation_core", Path("backend/app/core/runtime_remediation.py"), True),
            LocalSignal("workflow_auto_remediation_runbook", Path("docs/runbooks/workflow-auto-remediation.md"), True),
            LocalSignal("actions_auto_operator_workflow", Path(".github/workflows/actions-auto-operator.yml")),
            LocalSignal("failure_pattern_report", Path("artifacts/failure-pattern-engine/failure-pattern-report.json"), json_status_path=("summary", "risk", "status")),
        ],
    }


def risk_from_maturity(maturity: int, warnings: int, missing: int) -> str:
    if maturity >= 85 and warnings == 0 and missing == 0:
        return "low"
    if maturity >= 65 and missing <= 1:
        return "medium"
    return "high"


def confidence_from_domains(domains: dict[str, dict[str, Any]]) -> str:
    passed = sum(1 for item in domains.values() if item["status"] == "passed")
    if passed >= 5:
        return "high"
    if passed >= 3:
        return "medium"
    return "low"


def next_actions(domains: dict[str, dict[str, Any]]) -> list[str]:
    actions: list[str] = []
    for name, domain in domains.items():
        if domain["status"] == "missing":
            actions.append(f"Publicar ou gerar evidencias locais para o dominio {name}.")
        elif domain["status"] in {"partial", "warning"}:
            actions.append(f"Completar sinais obrigatorios e revisar alertas do dominio {name}.")
    return actions or ["Manter coleta local em CI e preparar contrato de dashboard/API sem rede externa."]


def build_report(root: Path) -> dict[str, Any]:
    domains = {name: evaluate_domain(name, signals, root) for name, signals in signal_catalog().items()}
    maturity = round(sum(domains[name]["score"] * DOMAIN_WEIGHTS[name] for name in DOMAIN_WEIGHTS))
    missing = sum(1 for item in domains.values() if item["status"] == "missing")
    warnings = sum(1 for item in domains.values() if item["status"] == "warning")
    return {
        "schema_version": "1.0.0",
        "report_type": "runtime_health_center",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "local_ci_read_only",
        "guardrails": ["no_network", "no_secrets", "no_deploy", "no_production_runtime_change"],
        "domains": domains,
        "maturity_percent": maturity,
        "operational_risk": risk_from_maturity(maturity, warnings, missing),
        "confidence_level": confidence_from_domains(domains),
        "next_required_actions": next_actions(domains),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate ReqSys Runtime Health Center report.")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    report = build_report(args.root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": args.output.as_posix(), "maturity_percent": report["maturity_percent"], "operational_risk": report["operational_risk"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
