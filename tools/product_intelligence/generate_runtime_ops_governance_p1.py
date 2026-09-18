#!/usr/bin/env python3
"""Generate ReqSys Runtime Ops Governance P1 artifacts.

This generator is intentionally read-only with regard to external systems. It
aggregates local evidence and produces reviewable governance artifacts for the
Runtime Health Center, CI auto-remediation, environment drift detection,
evidence consolidation, and runtime governance engine.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports" / "runtime-ops-governance"
DOC_PATH = ROOT / "docs" / "operations" / "runtime-ops-governance-p1.md"

LOCAL_EVIDENCE = {
    "ci_analytics": ROOT / "reports" / "github-runtime-analytics" / "github-runtime-analytics.json",
    "operational_timeline": ROOT / "reports" / "github-runtime-analytics" / "runtime-operational-correlation-timeline.json",
    "evidence_graph": ROOT / "reports" / "github-runtime-analytics" / "runtime-operational-evidence-graph.json",
    "health_dashboard": ROOT / "docs" / "operations" / "operational-health-dashboard.example.json",
    "product_readiness": ROOT / "reports" / "product-intelligence" / "product-intelligence-runtime-readiness-gate.json",
}

ENVIRONMENTS = ("dev", "hml", "prod", "flyio")
REQUIRED_ENV_KEYS = (
    "APP_ENV",
    "DATABASE_URL",
    "JWT_ISSUER",
    "JWT_AUDIENCE",
    "JWT_EXP_MINUTES",
    "CORS_ORIGINS",
)
SECRET_KEYS = ("JWT_SECRET", "FLY_API_TOKEN", "GITHUB_TOKEN")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"json root must be object: {path}")
    return payload


def evidence_inventory() -> dict[str, Any]:
    items: dict[str, Any] = {}
    for name, path in LOCAL_EVIDENCE.items():
        payload = read_json(path)
        items[name] = {
            "path": str(path.relative_to(ROOT)),
            "present": path.exists(),
            "state": payload.get("runtime_state") or payload.get("gate_status") or payload.get("status") or "UNKNOWN",
        }
    return items


def classify_ci_failure(message: str) -> dict[str, str]:
    normalized = message.lower()
    if "missing_export" in normalized or "does not provide an export named" in normalized:
        return {"class": "frontend_contract", "safe_action": "apply focused import/export fix and rebuild"}
    if "timeout" in normalized or "rate limit" in normalized:
        return {"class": "transient_infrastructure", "safe_action": "single governed rerun after cooldown"}
    if "npm audit" in normalized or "pip-audit" in normalized:
        return {"class": "dependency_security", "safe_action": "block deploy and open dependency remediation"}
    if "pytest" in normalized or "assert" in normalized:
        return {"class": "regression", "safe_action": "block rerun-only strategy; require code/test fix"}
    return {"class": "unknown", "safe_action": "preserve evidence and request human triage"}


def build_environment_matrix() -> list[dict[str, Any]]:
    matrix: list[dict[str, Any]] = []
    for env in ENVIRONMENTS:
        matrix.append(
            {
                "environment": env,
                "required_variables": list(REQUIRED_ENV_KEYS),
                "secret_fingerprints_required": list(SECRET_KEYS),
                "checks": [
                    "health endpoint reachable",
                    "deployed version matches release evidence",
                    "migration head matches expected revision",
                    "required variables present without exposing values",
                    "secret presence compared by fingerprint only",
                ],
                "external_mutation": "disabled",
            }
        )
    return matrix


def score_governance(inventory: dict[str, Any]) -> dict[str, Any]:
    present = sum(1 for item in inventory.values() if item["present"])
    evidence_score = round((present / max(len(inventory), 1)) * 100)
    drift_score = 70 if present else 40
    remediation_score = 65
    health_score = round((evidence_score * 0.45) + (drift_score * 0.25) + (remediation_score * 0.30))
    if health_score >= 85:
        state = "GOVERNED_READY"
    elif health_score >= 60:
        state = "READY_WITH_GAPS"
    else:
        state = "NOT_READY"
    return {
        "health_score": health_score,
        "state": state,
        "deployment_confidence": "medium" if state == "READY_WITH_GAPS" else "high" if state == "GOVERNED_READY" else "low",
        "rollback_policy": "manual approval required with pre/post evidence snapshots",
    }


def build_payload() -> dict[str, Any]:
    inventory = evidence_inventory()
    governance = score_governance(inventory)
    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "name": "runtime-ops-governance-p1",
        "mode": "review_only",
        "runtime_health_center": {
            "sources": inventory,
            "coverage": ["CI", "PRs", "workflows", "Fly.io", "environments", "coverage", "drift", "evidence", "analytics"],
        },
        "ci_auto_remediation": {
            "rerun_policy": "one safe rerun only for transient_infrastructure after evidence snapshot",
            "known_failure_taxonomy": [
                classify_ci_failure("MISSING_EXPORT"),
                classify_ci_failure("timeout"),
                classify_ci_failure("npm audit"),
                classify_ci_failure("pytest assert"),
            ],
            "auto_fix_scope": "lightweight, focused, non-secret, non-deploy changes only",
        },
        "environment_drift_detector": {
            "environments": build_environment_matrix(),
            "secret_policy": "compare presence/fingerprint metadata only; never persist secret values",
        },
        "runtime_evidence_consolidator": {
            "artifacts": [
                "runtime-ops-governance-p1.json",
                "runtime-ops-governance-p1.md",
                "runtime-ops-governance-p1.html",
            ],
            "executive_report": "enabled",
            "maturity_score": governance["health_score"],
        },
        "runtime_governance_engine": governance,
        "limits": ["no_deploy", "no_external_write", "no_secret_value_capture", "human_review_required"],
        "next_recommended_increment": "runtime-ops-governance-p2-live-connectors",
    }


def write_reports(payload: dict[str, Any], report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "runtime-ops-governance-p1.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    sources = payload["runtime_health_center"]["sources"]
    source_rows = "\n".join(
        f"| {name} | {item['present']} | `{item['state']}` | `{item['path']}` |" for name, item in sources.items()
    )
    taxonomy_rows = "\n".join(
        f"| `{item['class']}` | {item['safe_action']} |" for item in payload["ci_auto_remediation"]["known_failure_taxonomy"]
    )
    env_rows = "\n".join(
        f"| {item['environment']} | {', '.join(item['required_variables'])} | fingerprint-only |" for item in payload["environment_drift_detector"]["environments"]
    )
    governance = payload["runtime_governance_engine"]
    markdown = f"""# Runtime Ops Governance P1

## Estado executivo

| Campo | Valor |
|---|---|
| Modo | `{payload['mode']}` |
| Estado | `{governance['state']}` |
| Health score | {governance['health_score']} |
| Deployment confidence | {governance['deployment_confidence']} |
| Rollback policy | {governance['rollback_policy']} |

## Runtime Health Center

| Fonte | Presente | Estado | Caminho |
|---|---:|---|---|
{source_rows}

## CI Auto Remediation

Política de rerun: {payload['ci_auto_remediation']['rerun_policy']}.

| Classe | Ação segura |
|---|---|
{taxonomy_rows}

## Environment Drift Detector

| Ambiente | Variáveis obrigatórias | Segredos |
|---|---|---|
{env_rows}

## Runtime Evidence Consolidator

Artefatos gerados:

"""
    markdown += "\n".join(f"- `{artifact}`" for artifact in payload["runtime_evidence_consolidator"]["artifacts"])
    markdown += "\n\n## Guardrails\n\n" + "\n".join(f"- `{limit}`" for limit in payload["limits"]) + "\n"
    (report_dir / "runtime-ops-governance-p1.md").write_text(markdown, encoding="utf-8")

    html = f"""<!DOCTYPE html>
<html lang=\"pt-BR\">
<head><meta charset=\"UTF-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\"><title>Runtime Ops Governance P1</title>
<style>body{{font-family:Arial,sans-serif;background:#020617;color:#e5e7eb;margin:0;padding:24px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}}.card{{background:#111827;border:1px solid #334155;border-radius:16px;padding:18px}}.metric{{font-size:30px;font-weight:700;color:#38bdf8}}code{{color:#fde68a}}</style></head>
<body><h1>Runtime Ops Governance P1</h1><div class=\"grid\"><div class=\"card\">Estado<div class=\"metric\">{governance['state']}</div></div><div class=\"card\">Health Score<div class=\"metric\">{governance['health_score']}</div></div><div class=\"card\">Confidence<div class=\"metric\">{governance['deployment_confidence']}</div></div></div><h2>Guardrails</h2><ul>{''.join(f'<li><code>{limit}</code></li>' for limit in payload['limits'])}</ul></body></html>"""
    (report_dir / "runtime-ops-governance-p1.html").write_text(html, encoding="utf-8")


def sync_doc(payload: dict[str, Any]) -> None:
    governance = payload["runtime_governance_engine"]
    content = f"""# Runtime Ops Governance P1

## Objetivo

Consolidar o primeiro incremento governado de operação autônoma do ReqSys, reduzindo reruns manuais, drift entre ambientes e retrabalho operacional.

## Entregas

1. **Runtime Health Center**: agrega evidências locais de CI, workflows, PRs, Fly.io, ambientes, cobertura, drift e analytics.
2. **CI Auto Remediation**: define taxonomia de falhas, política de rerun seguro e escopo permitido para autocorreções leves.
3. **Environment Drift Detector**: padroniza comparação dev/hml/prod/Fly.io sem persistir valores de segredos.
4. **Runtime Evidence Consolidator**: gera snapshots JSON, Markdown e HTML para auditoria e relato executivo.
5. **Runtime Governance Engine**: calcula health score, confidence de deploy, política de rollback e limites operacionais.

## Estado atual do P1

| Campo | Valor |
|---|---|
| Modo | `review_only` |
| Estado calculado | `{governance['state']}` |
| Health score inicial | {governance['health_score']} |
| Deployment confidence | `{governance['deployment_confidence']}` |
| Próximo incremento | `{payload['next_recommended_increment']}` |

## Comando operacional

```bash
python tools/product_intelligence/generate_runtime_ops_governance_p1.py
```

## Guardrails

- Não executa deploy.
- Não escreve em sistemas externos.
- Não captura valores de segredos.
- Não faz merge automático.
- Exige revisão humana antes de promoção de ambiente.
"""
    DOC_PATH.write_text(content, encoding="utf-8")


def main() -> int:
    payload = build_payload()
    write_reports(payload, REPORT_DIR)
    sync_doc(payload)
    print(f"Runtime Ops Governance P1: {payload['runtime_governance_engine']['state']} ({payload['runtime_governance_engine']['health_score']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
