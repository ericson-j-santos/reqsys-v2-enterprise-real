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
    "evidence_gate": 0.16,
    "governance": 0.14,
    "runtime_risk": 0.14,
    "living_architecture": 0.14,
    "environment": 0.14,
    "remediation": 0.06,
}
DEFAULT_OUTPUT = Path("artifacts/runtime-health-center/runtime-health-report.json")


ARTIFACT_CATALOG = {
    "runtime_health_validator": Path("artifacts/runtime-health-validator/runtime-health-validator.json"),
    "runtime_operational_evidence_graph": Path("artifacts/runtime-operational-evidence-graph/runtime-operational-evidence-graph.json"),
    "operational_risk_engine": Path("artifacts/operational-risk-engine/operational-risk-engine.json"),
    "operational_stability_score": Path("artifacts/operational-stability-score/operational-stability-score.json"),
    "pr_evidence_gate": Path("artifacts/pr-evidence-gate/pr-evidence-gate.json"),
    "public_runtime_evidence": Path("artifacts/public-runtime-evidence/public-runtime-evidence.json"),
    "public_access_validation": Path("artifacts/public-access-validation/public-access-validation.json"),
}

SENSITIVE_ENV_MARKERS = ("SECRET", "TOKEN", "PASSWORD", "PASS", "KEY")


def artifact_status(data: dict[str, Any] | None, exists: bool) -> str:
    if data and data.get("_parse_error"):
        return "warning"
    candidates = (
        ("status",),
        ("conclusion",),
        ("summary", "status"),
        ("summary", "risk", "status"),
        ("gate", "status"),
    )
    for path in candidates:
        value = nested_value(data, path)
        if value is not None:
            return normalize_status(value, exists)
    return normalize_status(None, exists)


def ingest_artifacts(root: Path) -> dict[str, Any]:
    artifacts = []
    for artifact_id, relative in ARTIFACT_CATALOG.items():
        absolute = root / relative
        data = load_json(absolute)
        exists = absolute.exists()
        artifacts.append({
            "id": artifact_id,
            "path": relative.as_posix(),
            "available": exists,
            "status": artifact_status(data, exists),
            "parse_error": bool(data and data.get("_parse_error")),
        })
    available = sum(1 for item in artifacts if item["available"])
    warnings = sum(1 for item in artifacts if item["status"] == "warning")
    return {
        "status": "passed" if available and warnings == 0 else "warning" if available else "missing",
        "artifacts_total": len(artifacts),
        "artifacts_available": available,
        "artifacts": artifacts,
    }


def extract_compose_signature(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    env_keys: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("-") or "=" not in stripped:
            continue
        key = stripped[1:].strip().split("=", 1)[0].strip()
        if key and not any(marker in key.upper() for marker in SENSITIVE_ENV_MARKERS):
            env_keys.add(key)
    return {
        "exists": path.exists(),
        "services": sorted({name for name in ("api", "frontend", "nginx") if f"  {name}:" in text}),
        "has_healthcheck": "healthcheck:" in text,
        "direct_api_ports": "${BACKEND_PORT" in text,
        "env_keys": sorted(env_keys),
        "uses_prod_env": "APP_ENV=production" in text,
        "uses_demo_login_false": "ALLOW_DEMO_LOGIN=false" in text,
    }


def classify_drift(issue_count: int, high_count: int, medium_count: int) -> str:
    if issue_count == 0:
        return "none"
    if high_count:
        return "high"
    if medium_count or issue_count >= 3:
        return "medium"
    return "low"


def detect_environment_drift(root: Path) -> dict[str, Any]:
    files = {
        "dev": Path("docker-compose.dev.yml"),
        "test": Path("docker-compose.test.yml"),
        "prod": Path("docker-compose.prod.yml"),
    }
    signatures = {env: extract_compose_signature(root / rel) for env, rel in files.items()}
    findings: list[dict[str, str]] = []
    for env, signature in signatures.items():
        if not signature["exists"]:
            findings.append({"severity": "high", "environment": env, "message": "arquivo de configuração ausente"})
    common_services = set(signatures["dev"]["services"]) & set(signatures["test"]["services"]) & set(signatures["prod"]["services"])
    if common_services != {"api", "frontend", "nginx"}:
        findings.append({"severity": "medium", "environment": "all", "message": "serviços base não estão alinhados entre dev/test/prod"})
    if signatures["prod"]["direct_api_ports"]:
        findings.append({"severity": "high", "environment": "prod", "message": "produção expõe porta direta do backend"})
    if not signatures["prod"]["has_healthcheck"]:
        findings.append({"severity": "medium", "environment": "prod", "message": "produção sem healthcheck local"})
    if not signatures["prod"]["uses_prod_env"] or not signatures["prod"]["uses_demo_login_false"]:
        findings.append({"severity": "high", "environment": "prod", "message": "gates produtivos APP_ENV/ALLOW_DEMO_LOGIN não detectados"})
    env_key_sets = {env: set(sig["env_keys"]) for env, sig in signatures.items()}
    prod_extra = sorted(env_key_sets["prod"] - env_key_sets["dev"] - env_key_sets["test"])
    if prod_extra:
        findings.append({"severity": "low", "environment": "prod", "message": "produção possui chaves operacionais extras esperadas", "keys": ",".join(prod_extra)})
    high = sum(1 for item in findings if item["severity"] == "high")
    medium = sum(1 for item in findings if item["severity"] == "medium")
    level = classify_drift(len(findings), high, medium)
    return {
        "status": "passed" if level in {"none", "low"} else "warning",
        "drift_level": level,
        "compared_environments": sorted(files),
        "files": {env: rel.as_posix() for env, rel in files.items()},
        "signatures": signatures,
        "findings": findings,
    }



def evaluate_public_access(root: Path) -> dict[str, Any]:
    relative = Path("artifacts/public-access-validation/public-access-validation.json")
    data = load_json(root / relative)
    if not data:
        return {"status": "missing", "path": relative.as_posix(), "available": False, "summary": None, "environments": {}}
    if data.get("_parse_error"):
        return {"status": "warning", "path": relative.as_posix(), "available": True, "summary": None, "environments": {}, "parse_error": True}
    analytics = data.get("analytics", {}) if isinstance(data.get("analytics"), dict) else {}
    by_env = analytics.get("byEnvironment", {}) if isinstance(analytics.get("byEnvironment"), dict) else {}
    envs: dict[str, Any] = {}
    for env, summary in by_env.items():
        total = int(summary.get("total") or 0)
        reachable = int(summary.get("reachable") or 0)
        expected = int(summary.get("expected") or 0)
        envs[env] = {
            "total": total,
            "reachable": reachable,
            "expected": expected,
            "status": "passed" if total and reachable == total and expected == total else "warning" if reachable else "missing",
        }
    total = int(analytics.get("total") or 0)
    reachable = int(analytics.get("reachable") or 0)
    expected = int(analytics.get("expected") or 0)
    status = "passed" if total and reachable == total and expected == total else "warning" if reachable else "missing"
    return {
        "status": status,
        "path": relative.as_posix(),
        "available": True,
        "generated_at": data.get("generatedAt"),
        "summary": {
            "total": total,
            "reachable": reachable,
            "expected": expected,
            "reachablePercent": analytics.get("reachablePercent"),
            "expectedPercent": analytics.get("expectedPercent"),
            "unavailable": analytics.get("unavailable"),
            "unexpectedStatus": analytics.get("unexpectedStatus"),
        },
        "environments": envs,
    }

def apply_drift_penalty(maturity: int, drift_level: str) -> int:
    penalties = {"none": 0, "low": 3, "medium": 10, "high": 20}
    return max(0, maturity - penalties.get(drift_level, 20))


def risk_with_drift(maturity: int, warnings: int, missing: int, drift_level: str) -> str:
    if drift_level == "high":
        return "high"
    if drift_level == "medium" and maturity < 85:
        return "high"
    if drift_level == "low" and maturity >= 85 and warnings == 0 and missing == 0:
        return "medium"
    return risk_from_maturity(maturity, warnings, missing)


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
        "evidence_gate": [
            LocalSignal("pr_evidence_gate_workflow", Path(".github/workflows/pr-evidence-gate.yml"), True),
            LocalSignal("pr_evidence_gate_contract_tests", Path("tests/test_pr_evidence_gate_workflow.py"), True),
            LocalSignal("public_runtime_evidence_workflow", Path(".github/workflows/public-runtime-evidence.yml"), True),
            LocalSignal("runtime_operational_evidence_graph", Path("artifacts/runtime-operational-evidence-graph/runtime-operational-evidence-graph.json"), json_status_path=("status",)),
        ],
        "governance": [
            LocalSignal("agents_operational_rules", Path("AGENTS.md"), True),
            LocalSignal("runtime_ops_p1_doc", Path("docs/operations/runtime-ops-governance-p1.md"), True),
            LocalSignal("governance_gate_workflow", Path(".github/workflows/operational-governance-gate.yml"), True),
            LocalSignal("governance_gate_report", Path("artifacts/operational-governance-gate/operational-governance-gate.json"), json_status_path=("status",)),
        ],
        "runtime_risk": [
            LocalSignal("runtime_risk_scoring_workflow", Path(".github/workflows/runtime-risk-scoring.yml"), True),
            LocalSignal("operational_risk_engine_workflow", Path(".github/workflows/operational-risk-engine.yml"), True),
            LocalSignal("runtime_health_validator_report", Path("artifacts/runtime-health-validator/runtime-health-validator.json"), json_status_path=("status",)),
            LocalSignal("operational_stability_score_artifact", Path("artifacts/operational-stability-score/operational-stability-score.json"), json_status_path=("status",)),
        ],
        "living_architecture": [
            LocalSignal("runtime_ops_governance_p1_doc", Path("docs/operations/runtime-ops-governance-p1.md"), True),
            LocalSignal("adr_directory", Path("docs/adr"), True),
            LocalSignal("runbooks_directory", Path("docs/runbooks"), True),
            LocalSignal("living_architecture_drift_artifact", Path("artifacts/living-architecture-doc-drift/living-architecture-doc-drift.json"), json_status_path=("status",)),
        ],
        "environment": [
            LocalSignal("dev_compose", Path("docker-compose.dev.yml"), True),
            LocalSignal("test_compose", Path("docker-compose.test.yml"), True),
            LocalSignal("prod_compose", Path("docker-compose.prod.yml"), True),
            LocalSignal("production_gate_tests", Path("backend/tests/test_security_production_gates.py"), True),
        ],
        "remediation": [
            LocalSignal("runtime_remediation_core", Path("backend/app/core/runtime_remediation.py"), True),
            LocalSignal("workflow_auto_remediation_runbook", Path("docs/runbooks/workflow-auto-remediation.md"), True),
            LocalSignal("actions_auto_operator_workflow", Path(".github/workflows/actions-auto-operator.yml")),
            LocalSignal("failure_pattern_report", Path("artifacts/failure-pattern-engine/failure-pattern-report.json"), json_status_path=("summary", "risk", "status")),
        ],
    }


def live_analytics_status(ingested_artifacts: dict[str, Any]) -> str:
    available = ingested_artifacts["artifacts_available"]
    if available >= 3:
        return "passed"
    if available:
        return "partial"
    return "missing"


def build_gold_standard_depth(
    domains: dict[str, dict[str, Any]],
    environment_drift: dict[str, Any],
    ingested_artifacts: dict[str, Any],
) -> dict[str, Any]:
    """Map existing signals to the six gold-standard deepening axes.

    This intentionally reuses the Runtime Health Center contract instead of
    creating another horizontal platform. All statuses are evidence-based and
    read-only.
    """
    axes = {
        "runtime": {
            "status": domains["runtime_risk"]["status"],
            "score": domains["runtime_risk"]["score"],
            "evidence": ["runtime_risk", "runtime_health_validator_report"],
            "operator_action": "Priorizar estabilizacao dos sinais runtime antes de ampliar novas frentes.",
        },
        "observability": {
            "status": ingested_artifacts["status"],
            "score": STATUS_SCORE[ingested_artifacts["status"]],
            "evidence": [artifact["id"] for artifact in ingested_artifacts["artifacts"] if artifact["available"]],
            "operator_action": "Publicar artifacts faltantes para reduzir diagnostico manual e manter trilha auditavel.",
        },
        "operational_ux": {
            "status": domains["governance"]["status"],
            "score": min(domains["governance"]["score"], domains["evidence_gate"]["score"]),
            "evidence": ["next_required_actions", "gold_standard_status", "pr_evidence_gate"],
            "operator_action": "Consumir next_required_actions como fila unica de operacao, evitando criar novos paineis paralelos.",
        },
        "live_analytics": {
            "status": live_analytics_status(ingested_artifacts),
            "score": STATUS_SCORE[live_analytics_status(ingested_artifacts)],
            "evidence": ["ingested_artifacts", "runtime_operational_evidence_graph"],
            "operator_action": "Evoluir serie historica a partir dos artifacts existentes, sem duplicar motores de analytics.",
        },
        "environments": {
            "status": environment_drift["status"],
            "score": STATUS_SCORE[environment_drift["status"]],
            "evidence": environment_drift["compared_environments"],
            "operator_action": "Corrigir drift medio/alto antes de promover dev -> hml -> prod.",
        },
        "autonomous_operation": {
            "status": domains["remediation"]["status"],
            "score": domains["remediation"]["score"],
            "evidence": ["remediation", "guardrails", "no_production_runtime_change"],
            "operator_action": "Manter automacao assistida e allowlisted ate evidenciar baixa recorrencia de falhas.",
        },
    }
    overall_score = round(sum(axis["score"] for axis in axes.values()) / len(axes))
    blockers = [name for name, axis in axes.items() if axis["status"] in {"missing", "warning"}]
    return {
        "strategy": "parar_expansao_horizontal_e_aprofundar_capacidades_existentes",
        "overall_score": overall_score,
        "overall_status": "passed" if overall_score >= 85 and not blockers else "warning" if overall_score >= 60 else "partial",
        "axes": axes,
        "blockers": blockers,
        "operational_focus_order": [
            "runtime",
            "observability",
            "operational_ux",
            "live_analytics",
            "environments",
            "autonomous_operation",
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
    ingested_artifacts = ingest_artifacts(root)
    environment_drift = detect_environment_drift(root)
    public_access = evaluate_public_access(root)
    domains["environment"]["status"] = environment_drift["status"] if domains["environment"]["status"] == "passed" else domains["environment"]["status"]
    if public_access["status"] != "missing":
        domains["environment"]["status"] = public_access["status"] if domains["environment"]["status"] == "passed" else domains["environment"]["status"]
    domains["environment"]["score"] = min(domains["environment"]["score"], STATUS_SCORE[domains["environment"]["status"]])
    base_maturity = round(sum(domains[name]["score"] * DOMAIN_WEIGHTS[name] for name in DOMAIN_WEIGHTS))
    maturity = apply_drift_penalty(base_maturity, environment_drift["drift_level"])
    missing = sum(1 for item in domains.values() if item["status"] == "missing")
    warnings = sum(1 for item in domains.values() if item["status"] == "warning")
    gold_standard = {
        "Runtime Health Center": "passed",
        "Operational Status Aggregator": "passed",
        "runtime-health-report.json": "passed",
        "Score consolidado de maturidade": "passed",
        "Environment Drift Detector": domains["environment"]["status"],
        "Remediation Executor governado": domains["remediation"]["status"],
    }
    gold_standard_depth = build_gold_standard_depth(domains, environment_drift, ingested_artifacts)
    return {
        "schema_version": "1.1.0",
        "report_type": "runtime_health_center",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "local_ci_read_only",
        "guardrails": ["no_network", "no_secrets", "no_deploy", "no_production_runtime_change"],
        "domains": domains,
        "ingested_artifacts": ingested_artifacts,
        "runtime_operational_evidence_graph": {"status": ingested_artifacts["status"], "source": "local_artifacts", "nodes": ingested_artifacts["artifacts_available"]},
        "runtime_risk_scoring": {"status": domains["runtime_risk"]["status"], "drift_level": environment_drift["drift_level"]},
        "pr_evidence_gate": {"status": domains["evidence_gate"]["status"], "duplicated": False},
        "environment_drift": environment_drift,
        "public_access_validation": public_access,
        "gold_standard_status": gold_standard,
        "gold_standard_depth": gold_standard_depth,
        "base_maturity_percent": base_maturity,
        "maturity_percent": maturity,
        "operational_risk": risk_with_drift(maturity, warnings, missing, environment_drift["drift_level"]),
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
