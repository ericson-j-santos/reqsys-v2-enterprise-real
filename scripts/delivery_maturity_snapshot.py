from __future__ import annotations

import argparse
import json
import os
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any
from uuid import uuid4

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.ci_intelligence_lib import (  # noqa: E402
    build_maturity_snapshot,
    calculate_maturity_trend,
    derive_maturity_signals,
    merge_maturity_history,
)

DIMENSIONS = [
    {
        "name": "técnico",
        "current_percent": 86.0,
        "target_percent": 98.0,
        "confidence_level": "medium",
        "evidence_links": [
            "docs/contracts/delivery-maturity-snapshot.schema.json",
            ".github/workflows/ci.yml",
            "docs/runbooks/operational-artifact-schema-validation.md",
        ],
        "next_recommended_action": "Executar CI completo e ampliar validação automatizada do schema antes de promover o snapshot de report-only para gate informativo.",
    },
    {
        "name": "operacional",
        "current_percent": 88.0,
        "target_percent": 98.0,
        "confidence_level": "medium",
        "evidence_links": [
            "docs/runbooks/operational-history-snapshots.md",
            "docs/runbooks/operational-burndown-executive.md",
            ".github/workflows/operational-history-snapshot.yml",
        ],
        "next_recommended_action": "Conectar histórico real dos artifacts de operação ao snapshot para reduzir inferência manual.",
    },
    {
        "name": "usuário final",
        "current_percent": 74.0,
        "target_percent": 95.0,
        "confidence_level": "low",
        "evidence_links": [
            "frontend/tests/e2e/responsividade.spec.js",
            "docs/runbooks/runtime-public-access-readiness.md",
        ],
        "next_recommended_action": "Coletar evidência E2E recente de jornada de usuário e anexar link do artifact antes de elevar confiança.",
    },
    {
        "name": "governança",
        "current_percent": 90.0,
        "target_percent": 99.0,
        "confidence_level": "medium",
        "evidence_links": [
            "AGENTS.md",
            "docs/dashboard/command-center-evidence-index.md",
            "docs/runbooks/delivery-evidence-index.md",
        ],
        "next_recommended_action": "Manter rastreabilidade artifact → contrato → dashboard e registrar exceções de PR draft até estabilização.",
    },
    {
        "name": "produção",
        "current_percent": 70.0,
        "target_percent": 98.0,
        "confidence_level": "low",
        "evidence_links": [
            "docs/runbooks/golden-release-operational-checklist.md",
            "docs/runbooks/public-runtime-evidence-gate.md",
            "AGENTS.md",
        ],
        "next_recommended_action": "Validar gates produtivos com evidência de ambiente publicado sem alterar runtime produtivo neste incremento.",
    },
    {
        "name": "observabilidade",
        "current_percent": 84.0,
        "target_percent": 98.0,
        "confidence_level": "medium",
        "evidence_links": [
            "docs/runbooks/runtime-operational-observability-v1.md",
            "docs/runbooks/runtime-correlation-analytics-foundation.md",
            ".github/workflows/runtime-health-center.yml",
        ],
        "next_recommended_action": "Integrar sinais de correlation_id, incident timeline e runtime health no dashboard dinâmico com histórico.",
    },
    {
        "name": "segurança",
        "current_percent": 82.0,
        "target_percent": 99.0,
        "confidence_level": "medium",
        "evidence_links": [
            "AGENTS.md",
            ".github/workflows/ci.yml",
            "docs/runbooks/public-runtime-evidence-gate.md",
        ],
        "next_recommended_action": "Anexar evidências recentes de ruff, pip-audit, bandit, npm audit e gates JWT/CORS antes de qualquer declaração consolidada.",
    },
    {
        "name": "evidência",
        "current_percent": 89.0,
        "target_percent": 99.0,
        "confidence_level": "medium",
        "evidence_links": [
            "docs/runbooks/delivery-evidence-index.md",
            "docs/dashboard/command-center-evidence-index.md",
            "docs/contracts/delivery-maturity-snapshot.schema.json",
        ],
        "next_recommended_action": "Publicar o artifact delivery-maturity-snapshot e referenciar execução real no índice de evidências.",
    },
]


def load_json(path: Path) -> dict[str, Any] | list[Any] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def semaphore(current: float, gap: float, confidence: str) -> str:
    if confidence == "low" or gap >= 20 or current < 75:
        return "vermelho"
    if gap > 5 or confidence == "medium":
        return "amarelo"
    return "verde"


def apply_signals(dimensions: list[dict[str, Any]], signals: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    updated: list[dict[str, Any]] = []
    for source in dimensions:
        item = deepcopy(source)
        override = signals.get(item["name"])
        if override:
            for key in ("current_percent", "confidence_level", "evidence_links", "next_recommended_action"):
                if key in override and override[key] is not None:
                    item[key] = override[key]
        item["gap_percent"] = round(item["target_percent"] - item["current_percent"], 2)
        item["status_semáforo"] = semaphore(item["current_percent"], item["gap_percent"], item["confidence_level"])
        item["state_type"] = "evidenced_current_state"
        updated.append(item)
    return updated


def build_report(
    ci_report: dict[str, Any] | None = None,
    pr_evidence: dict[str, Any] | None = None,
    coordenador: dict[str, Any] | None = None,
    head_sha: str | None = None,
    history: list[dict[str, Any]] | None = None,
    max_history_items: int = 120,
) -> dict[str, Any]:
    sources: dict[str, str] = {}
    if ci_report:
        sources["operational_ci_intelligence"] = "artifacts/operational-ci-intelligence/operational-ci-intelligence.json"
    if pr_evidence:
        sources["pr_evidence_gate"] = "audit/pr-evidence-gate.json"
    if coordenador:
        sources["coordenador_status"] = "artifacts/coordenador-status-evidence/coordenador-status.json"

    signals = derive_maturity_signals(ci_report, pr_evidence, coordenador)
    dimensions = apply_signals(DIMENSIONS, signals)

    dynamic_names = set(signals.keys())
    dynamic_scores = [item["current_percent"] for item in dimensions if item["name"] in dynamic_names]
    static_scores = [item["current_percent"] for item in dimensions if item["name"] not in dynamic_names]
    if dynamic_scores:
        continuous_score = round((sum(dynamic_scores) + sum(static_scores)) / len(dimensions), 2)
    else:
        continuous_score = round(mean(item["current_percent"] for item in dimensions), 2)

    generated_at = datetime.now(timezone.utc).isoformat()
    report = {
        "schema_version": "1.1.0",
        "generated_at": generated_at,
        "repository": os.getenv("REPOSITORY", os.getenv("GITHUB_REPOSITORY", "local")),
        "run_id": os.getenv("RUN_ID", os.getenv("GITHUB_RUN_ID", "local")),
        "event_name": os.getenv("EVENT_NAME", os.getenv("GITHUB_EVENT_NAME", "local")),
        "head_sha": head_sha,
        "correlation_id": str(uuid4()),
        "mode": "report_only",
        "runtime_impact": "none",
        "consolidation_policy": "Não declarar status consolidado sem evidência anexada; estado atual evidenciado e estado alvo permanecem separados.",
        "continuous_score": continuous_score,
        "average_current_percent": round(mean(item["current_percent"] for item in dimensions), 2),
        "average_target_percent": round(mean(item["target_percent"] for item in dimensions), 2),
        "average_gap_percent": round(mean(item["gap_percent"] for item in dimensions), 2),
        "lowest_dimension": min(dimensions, key=lambda item: item["current_percent"])["name"],
        "highest_gap_dimension": max(dimensions, key=lambda item: item["gap_percent"])["name"],
        "sources": sources,
        "dimensions": dimensions,
    }

    snapshot = build_maturity_snapshot(report, head_sha=head_sha)
    merged_history = merge_maturity_history(history or [], snapshot, max_history_items)
    trend = calculate_maturity_trend(merged_history)
    report["maturity_history"] = {
        "snapshot": snapshot,
        "trend": trend,
        "points": len(merged_history),
        "history": merged_history,
    }
    return report


def write_markdown(report: dict[str, Any], path: Path) -> None:
    trend = (report.get("maturity_history") or {}).get("trend") or {}
    lines = [
        "# Delivery Maturity Snapshot",
        "",
        f"- Modo: `{report['mode']}`",
        f"- Impacto runtime: `{report['runtime_impact']}`",
        f"- Score contínuo: {report.get('continuous_score', report['average_current_percent'])}%",
        f"- Média atual evidenciada: {report['average_current_percent']}%",
        f"- Média alvo: {report['average_target_percent']}%",
        f"- Gap médio: {report['average_gap_percent']} p.p.",
        f"- Maior gap: {report['highest_gap_dimension']}",
        f"- Head SHA: `{report.get('head_sha') or 'n/d'}`",
        f"- Fontes: `{json.dumps(report.get('sources', {}), ensure_ascii=False)}`",
        "",
        "## Tendência de maturidade",
        "",
        f"- Direção: `{trend.get('direction', 'unknown')}`",
        f"- Delta score: `{trend.get('delta_score', 0)}`",
        f"- Pontos históricos: `{(report.get('maturity_history') or {}).get('points', 0)}`",
        "",
        "> Estado atual e alvo são separados. Nenhum status é declarado como consolidado sem evidência explícita.",
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
    parser = argparse.ArgumentParser(description="Generate delivery maturity snapshot with optional live evidence sources.")
    parser.add_argument("--ci-report", type=Path, help="Operational CI Intelligence JSON report.")
    parser.add_argument("--pr-evidence", type=Path, help="PR Evidence Gate audit JSON.")
    parser.add_argument("--coordenador-status", type=Path, help="Coordenador status consolidated JSON.")
    parser.add_argument("--head-sha", type=str, default=os.getenv("HEAD_SHA", ""))
    parser.add_argument("--history", type=Path, default=Path("data/delivery-maturity-history/maturity-history.json"))
    parser.add_argument("--out-dir", type=Path, default=Path(os.getenv("OUTPUT_DIR", "audit/delivery-maturity")))
    parser.add_argument("--max-history-items", type=int, default=120)
    args = parser.parse_args()

    ci_report = load_json(args.ci_report) if args.ci_report else None
    pr_evidence = load_json(args.pr_evidence) if args.pr_evidence else None
    coordenador = load_json(args.coordenador_status) if args.coordenador_status else None
    existing_history = load_json(args.history) if args.history else []
    if not isinstance(existing_history, list):
        existing_history = []

    report = build_report(
        ci_report=ci_report if isinstance(ci_report, dict) else None,
        pr_evidence=pr_evidence if isinstance(pr_evidence, dict) else None,
        coordenador=coordenador if isinstance(coordenador, dict) else None,
        head_sha=args.head_sha or None,
        history=existing_history,
        max_history_items=args.max_history_items,
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    args.history.parent.mkdir(parents=True, exist_ok=True)
    merged_history = report["maturity_history"]["history"]
    args.history.write_text(json.dumps(merged_history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    (args.out_dir / "delivery-maturity-snapshot.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    write_markdown(report, args.out_dir / "delivery-maturity-snapshot.md")
    (args.out_dir / "maturity-history.json").write_text(
        json.dumps(merged_history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
