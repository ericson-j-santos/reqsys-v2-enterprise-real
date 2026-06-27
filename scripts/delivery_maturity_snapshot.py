from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

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


def semaphore(current: float, gap: float, confidence: str) -> str:
    if confidence == "low" or gap >= 20 or current < 75:
        return "vermelho"
    if gap > 5 or confidence == "medium":
        return "amarelo"
    return "verde"


def build_report() -> dict:
    dimensions = []
    for source in DIMENSIONS:
        item = dict(source)
        item["gap_percent"] = round(item["target_percent"] - item["current_percent"], 2)
        item["status_semáforo"] = semaphore(item["current_percent"], item["gap_percent"], item["confidence_level"])
        item["state_type"] = "evidenced_current_state"
        dimensions.append(item)

    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": os.getenv("REPOSITORY", os.getenv("GITHUB_REPOSITORY", "local")),
        "run_id": os.getenv("RUN_ID", os.getenv("GITHUB_RUN_ID", "local")),
        "event_name": os.getenv("EVENT_NAME", os.getenv("GITHUB_EVENT_NAME", "local")),
        "mode": "report_only",
        "runtime_impact": "none",
        "consolidation_policy": "Não declarar status consolidado sem evidência anexada; estado atual evidenciado e estado alvo permanecem separados.",
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
    out_dir = Path(os.getenv("OUTPUT_DIR", "audit/delivery-maturity"))
    out_dir.mkdir(parents=True, exist_ok=True)
    report = build_report()
    (out_dir / "delivery-maturity-snapshot.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_markdown(report, out_dir / "delivery-maturity-snapshot.md")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
