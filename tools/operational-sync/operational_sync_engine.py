from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class OperationalTask:
    id: str
    title: str
    source: str
    status: str
    impact: int
    production_risk: int
    recurrence: int
    blocked_minutes: int
    dependencies: int
    urgency: int
    evidence: list[str]

    @property
    def risk_score(self) -> int:
        score = (
            self.impact * 0.35
            + self.production_risk * 0.25
            + self.recurrence * 0.15
            + min(self.blocked_minutes / 60, 100) * 0.10
            + self.dependencies * 0.10
            + self.urgency * 0.05
        )
        return round(score)

    @property
    def severity(self) -> str:
        if self.risk_score >= 85:
            return "critico"
        if self.risk_score >= 70:
            return "alto"
        if self.risk_score >= 45:
            return "medio"
        return "baixo"


def _default_tasks() -> list[OperationalTask]:
    return [
        OperationalTask(
            id="ROC-PR-081",
            title="Validar PR #81 - Analytics Runtime Intelligence e retorno Figma",
            source="github",
            status="verde_em_draft",
            impact=78,
            production_risk=40,
            recurrence=25,
            blocked_minutes=0,
            dependencies=30,
            urgency=60,
            evidence=["CI principal verde", "Governanca Padrao Ouro verde", "Governance Quality Gates verde"],
        ),
        OperationalTask(
            id="ROC-PR-082",
            title="Monitorar PR #82 - falha em testes backend",
            source="github",
            status="acao_requerida",
            impact=82,
            production_risk=65,
            recurrence=55,
            blocked_minutes=30,
            dependencies=45,
            urgency=75,
            evidence=["Backend Tests + Coverage falhou", "lint/security e frontend verdes"],
        ),
        OperationalTask(
            id="ROC-FIGMA-001",
            title="Materializar retorno visual Figma/FigJam para fluxo operacional",
            source="figma",
            status="implementado_com_fallback",
            impact=70,
            production_risk=20,
            recurrence=35,
            blocked_minutes=0,
            dependencies=50,
            urgency=55,
            evidence=["Diagrama Mermaid versionado", "Relatorio HTML autocontido"],
        ),
    ]


def build_snapshot(tasks: Iterable[OperationalTask]) -> dict[str, object]:
    task_list = list(tasks)
    total = len(task_list)
    critical = sum(1 for task in task_list if task.severity == "critico")
    high = sum(1 for task in task_list if task.severity == "alto")
    average = round(sum(task.risk_score for task in task_list) / total, 2) if total else 0
    status = "acao_requerida" if critical or high else "estavel"

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "capability": "Operational Sync Engine v1",
        "correlation_id": f"roc-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}",
        "status": status,
        "risk_average": average,
        "tasks_total": total,
        "tasks_high_or_critical": critical + high,
        "guard_rails": [
            "sem_segredos_em_logs",
            "sem_execucao_produtiva_sem_aprovacao",
            "correlation_id_obrigatorio",
            "html_autocontido_obrigatorio",
            "figma_retorno_visual_obrigatorio_quando_disponivel",
        ],
        "tasks": [asdict(task) | {"risk_score": task.risk_score, "severity": task.severity} for task in task_list],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera snapshot operacional auditavel do ReqSys ROC.")
    parser.add_argument("--output", default="artifacts/operational-sync-snapshot.json")
    args = parser.parse_args()

    snapshot = build_snapshot(_default_tasks())
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    github_summary = os.getenv("GITHUB_STEP_SUMMARY")
    if github_summary:
        Path(github_summary).write_text(
            "# Operational Sync Engine v1\n\n"
            f"Status: **{snapshot['status']}**\n\n"
            f"Risco medio: **{snapshot['risk_average']}**\n\n"
            f"Tarefas monitoradas: **{snapshot['tasks_total']}**\n",
            encoding="utf-8",
        )

    print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
