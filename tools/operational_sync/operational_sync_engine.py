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

    @classmethod
    def from_dict(cls, payload: dict) -> 'OperationalTask':
        required = {
            'id', 'title', 'source', 'status', 'impact', 'production_risk',
            'recurrence', 'blocked_minutes', 'dependencies', 'urgency', 'evidence',
        }
        missing = sorted(required - payload.keys())
        if missing:
            raise ValueError(f'campos obrigatórios ausentes: {", ".join(missing)}')
        return cls(**{key: payload[key] for key in required})

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
        return max(0, min(100, round(score)))

    @property
    def severity(self) -> str:
        if self.risk_score >= 85:
            return 'critico'
        if self.risk_score >= 70:
            return 'alto'
        if self.risk_score >= 45:
            return 'medio'
        return 'baixo'


def load_tasks(path: str | None) -> list[OperationalTask]:
    if not path:
        return []
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(payload, list):
        raise ValueError('o input do Operational Sync deve ser uma lista JSON')
    return [OperationalTask.from_dict(item) for item in payload]


def build_snapshot(tasks: Iterable[OperationalTask], correlation_id: str | None = None) -> dict[str, object]:
    task_list = list(tasks)
    total = len(task_list)
    critical = sum(1 for task in task_list if task.severity == 'critico')
    high = sum(1 for task in task_list if task.severity == 'alto')
    average = round(sum(task.risk_score for task in task_list) / total, 2) if total else None

    if not task_list:
        status = 'evidence_required'
    elif critical or high:
        status = 'acao_requerida'
    else:
        status = 'estavel'

    resolved_correlation = correlation_id or (
        f"github-actions-{os.getenv('GITHUB_RUN_ID')}-{(os.getenv('GITHUB_SHA') or 'unknown')[:12]}"
        if os.getenv('GITHUB_RUN_ID')
        else 'local-contract-validation'
    )

    return {
        'schema_version': '1.1.0',
        'generated_at': datetime.now(UTC).isoformat(),
        'capability': 'Operational Sync Engine',
        'correlation_id': resolved_correlation,
        'status': status,
        'operational_evidence': bool(task_list),
        'risk_average': average,
        'tasks_total': total,
        'tasks_high_or_critical': critical + high,
        'guard_rails': [
            'sem_segredos_em_logs',
            'sem_execucao_produtiva_sem_aprovacao',
            'correlation_id_obrigatorio',
            'evidencia_externa_nao_pode_ser_inventada',
        ],
        'tasks': [asdict(task) | {'risk_score': task.risk_score, 'severity': task.severity} for task in task_list],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Gera snapshot auditável a partir de evidência operacional fornecida.')
    parser.add_argument('--input', help='JSON com tarefas/evidências reais. Ausente => evidence_required.')
    parser.add_argument('--output', default='artifacts/operational-sync-snapshot.json')
    args = parser.parse_args()

    snapshot = build_snapshot(load_tasks(args.input))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
