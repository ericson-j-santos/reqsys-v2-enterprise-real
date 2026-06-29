from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DIMENSION_TARGETS = {
    "técnico": 100.0,
    "operacional": 100.0,
    "usuário final": 100.0,
    "governança": 100.0,
    "produção": 100.0,
    "observabilidade": 100.0,
    "segurança": 100.0,
    "evidência": 100.0,
}

DIMENSION_EVIDENCE = {
    "técnico": [
        ".github/workflows/ci.yml",
        "artifacts/runtime-health-center/runtime-health-report.json",
        "docs/contracts/delivery-maturity-snapshot.schema.json",
    ],
    "operacional": [
        "docs/runbooks/operational-history-snapshots.md",
        "artifacts/runtime-health-center/runtime-health-report.json",
        ".github/workflows/operational-history-snapshot.yml",
    ],
    "usuário final": [
        "frontend/tests/e2e/responsividade.spec.js",
        "audit/runtime/public-runtime-validation.json",
    ],
    "governança": [
        "AGENTS.md",
        "audit/trilhas/trilhas-padrao-ouro-report.json",
        "docs/dashboard/command-center-evidence-index.md",
    ],
    "produção": [
        "audit/runtime/public-runtime-validation.json",
        "docs/runbooks/golden-release-operational-checklist.md",
        "artifacts/public-access-validation/public-access-validation.json",
    ],
    "observabilidade": [
        ".github/workflows/runtime-health-center.yml",
        "artifacts/runtime-health-center/runtime-health-report.json",
        "docs/runbooks/runtime-operational-observability-v1.md",
    ],
    "segurança": [
        "AGENTS.md",
        ".github/workflows/ci.yml",
        "backend/tests/test_security_production_gates.py",
    ],
    "evidência": [
        "docs/runbooks/delivery-evidence-index.md",
        "docs/dashboard/command-center-evidence-index.md",
        "audit/runtime/public-runtime-evidence-index.json",
    ],
}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def _runtime_report(root: Path) -> dict[str, Any]:
    return _load_json(root / "artifacts/runtime-health-center/runtime-health-report.json")


def _public_runtime(root: Path) -> dict[str, Any]:
    for relative in (
        "audit/runtime/public-runtime-validation.json",
        "artifacts/runtime/public-runtime-validation.json",
    ):
        payload = _load_json(root / relative)
        if payload:
            return payload
    return {}


def _trilhas_report(root: Path) -> dict[str, Any]:
    return _load_json(root / "audit/trilhas/trilhas-padrao-ouro-report.json")


def _dashboard_regression(root: Path) -> dict[str, Any]:
    return _load_json(root / "docs/dashboard/dashboard-regression-report.json")


def compute_dimension_scores(root: Path) -> dict[str, float]:
    runtime = _runtime_report(root)
    public = _public_runtime(root)
    trilhas = _trilhas_report(root)
    regression = _dashboard_regression(root)
    readiness = public.get("readiness") or {}
    domains = runtime.get("domains") or {}
    depth = runtime.get("gold_standard_depth") or {}
    axes = depth.get("axes") or {}

    runtime_readiness = float(readiness.get("readiness_percent") or 0)
    trilhas_pct = float((trilhas.get("summary") or {}).get("gold_standard_percent") or 0)
    maturity_pct = float(runtime.get("maturity_percent") or 0)
    depth_pct = float(depth.get("overall_score") or 0)
    regression_passed = int((regression.get("summary") or {}).get("passed") or 0)
    regression_checks = int((regression.get("summary") or {}).get("checks") or 0)
    regression_pct = 100.0 if regression_checks and regression_passed == regression_checks else 0.0

    e2e_exists = (root / "frontend/tests/e2e/responsividade.spec.js").exists()
    security_exists = (root / "backend/tests/test_security_production_gates.py").exists()

    return {
        "técnico": _clamp(float(domains.get("ci_cd", {}).get("score") or maturity_pct or 0)),
        "operacional": _clamp(max(float(domains.get("governance", {}).get("score") or 0), depth_pct, maturity_pct)),
        "usuário final": _clamp(runtime_readiness if e2e_exists else min(runtime_readiness, 95.0)),
        "governança": _clamp(max(trilhas_pct, float(domains.get("governance", {}).get("score") or 0))),
        "produção": _clamp(runtime_readiness),
        "observabilidade": _clamp(float(axes.get("observability", {}).get("score") or maturity_pct or 0)),
        "segurança": _clamp(100.0 if security_exists and float(domains.get("environment", {}).get("score") or 0) >= 100 else float(domains.get("environment", {}).get("score") or 0)),
        "evidência": _clamp(max(regression_pct, depth_pct, float((runtime.get("ingested_artifacts") or {}).get("artifacts_available", 0) / max((runtime.get("ingested_artifacts") or {}).get("artifacts_total", 1), 1) * 100))),
    }


def confidence_for(score: float, evidence_links: list[str], root: Path) -> str:
    existing = sum(1 for link in evidence_links if (root / link).exists())
    if score >= 100 and existing == len(evidence_links):
        return "high"
    if score >= 90:
        return "medium"
    return "low"


def next_action_for(name: str, score: float, target: float) -> str:
    if score >= target:
        return "Manter evidência consolidada e monitorar regressão report-only."
    return {
        "técnico": "Executar CI completo e ampliar validação automatizada do schema.",
        "operacional": "Conectar histórico real dos artifacts de operação ao snapshot.",
        "usuário final": "Coletar evidência E2E recente de jornada de usuário.",
        "governança": "Manter rastreabilidade artifact → contrato → dashboard.",
        "produção": "Validar gates produtivos com evidência de ambiente publicado.",
        "observabilidade": "Integrar sinais de correlation_id e runtime health no dashboard dinâmico.",
        "segurança": "Anexar evidências recentes de ruff, pip-audit, bandit e npm audit.",
        "evidência": "Publicar artifacts e referenciar execução real no índice de evidências.",
    }.get(name, "Completar evidências faltantes antes de promover o snapshot.")


def semaphore(current: float, gap: float, confidence: str) -> str:
    if confidence == "low" or gap >= 20 or current < 75:
        return "vermelho"
    if gap > 0 or confidence == "medium":
        return "amarelo"
    return "verde"


def build_report(root: Path | None = None) -> dict:
    root = root or ROOT
    scores = compute_dimension_scores(root)
    dimensions = []
    for name, target in DIMENSION_TARGETS.items():
        current = round(scores[name], 2)
        gap = round(target - current, 2)
        evidence_links = DIMENSION_EVIDENCE[name]
        confidence = confidence_for(current, evidence_links, root)
        dimensions.append(
            {
                "name": name,
                "current_percent": current,
                "target_percent": target,
                "confidence_level": confidence,
                "evidence_links": evidence_links,
                "next_recommended_action": next_action_for(name, current, target),
                "gap_percent": gap,
                "status_semáforo": semaphore(current, gap, confidence),
                "state_type": "evidenced_current_state",
            }
        )

    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": os.getenv("REPOSITORY", os.getenv("GITHUB_REPOSITORY", "local")),
        "run_id": os.getenv("RUN_ID", os.getenv("GITHUB_RUN_ID", "local")),
        "event_name": os.getenv("EVENT_NAME", os.getenv("GITHUB_EVENT_NAME", "local")),
        "mode": "report_only",
        "runtime_impact": "none",
        "consolidation_policy": "Estado atual derivado de artifacts versionados; alvo permanece separado.",
        "average_current_percent": round(mean(item["current_percent"] for item in dimensions), 2),
        "average_target_percent": round(mean(item["target_percent"] for item in dimensions), 2),
        "average_gap_percent": round(mean(item["gap_percent"] for item in dimensions), 2),
        "lowest_dimension": min(dimensions, key=lambda item: item["current_percent"])["name"],
        "highest_gap_dimension": max(dimensions, key=lambda item: item["gap_percent"])["name"],
        "dimensions": dimensions,
    }


def write_markdown(report: dict, path: Path) -> None:
    lines = [
        "# Delivery Maturity Snapshot",
        "",
        f"- Modo: `{report['mode']}`",
        f"- Impacto runtime: `{report['runtime_impact']}`",
        f"- Média atual evidenciada: {report['average_current_percent']}%",
        f"- Média alvo: {report['average_target_percent']}%",
        f"- Gap médio: {report['average_gap_percent']} p.p.",
        f"- Maior gap: {report['highest_gap_dimension']}",
        "",
        "> Estado atual derivado de artifacts versionados.",
        "",
        "## Dimensões",
        "",
        "| Dimensão | Atual | Alvo | Gap | Semáforo | Confiança | Próxima ação |",
        "| --- | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for item in report["dimensions"]:
        lines.append(
            f"| {item['name']} | {item['current_percent']}% | {item['target_percent']}% | {item['gap_percent']} p.p. | {item['status_semáforo']} | {item['confidence_level']} | {item['next_recommended_action']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    out_dir = Path(os.getenv("OUTPUT_DIR", "audit/delivery-maturity"))
    out_dir.mkdir(parents=True, exist_ok=True)
    report = build_report()
    (out_dir / "delivery-maturity-snapshot.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_markdown(report, out_dir / "delivery-maturity-snapshot.md")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
