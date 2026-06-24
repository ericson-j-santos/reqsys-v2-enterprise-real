#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def load_json(path: Path, default):
    if not path.exists():
        return default
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


def classify_risk(score: float) -> str:
    if score >= 80:
        return 'BAIXO'
    if score >= 60:
        return 'MEDIO'
    if score >= 40:
        return 'ALTO'
    return 'CRITICO'


def calculate_risk(history: list, governance: dict) -> dict:
    latest = history[-1] if history else {}
    metrics = latest.get('metrics', {})

    failure_rate = float(metrics.get('overall_failure_rate_percent') or 0)
    mttr = float(metrics.get('mttr_minutes') or 0)
    hub_score = float(latest.get('hub_score') or 0)

    governance_blocked = governance.get('gate_status') == 'BLOCKED'

    risk_score = 100 - hub_score
    risk_score += min(failure_rate, 40)
    risk_score += min(mttr / 10, 20)

    if governance_blocked:
        risk_score += 15

    risk_score = min(round(risk_score, 2), 100)

    workflows = latest.get('workflow_failure_rates', [])
    critical_workflows = [
        item for item in workflows
        if float(item.get('failure_rate_percent') or 0) >= 40
    ]

    direction = 'ESTAVEL'
    if len(history) >= 2:
        prev = float(history[-2].get('hub_score') or 0)
        if hub_score > prev + 3:
            direction = 'MELHORANDO'
        elif hub_score < prev - 3:
            direction = 'PIORANDO'

    return {
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'risk_score': risk_score,
        'risk_level': classify_risk(100 - risk_score),
        'trend_direction': direction,
        'failure_rate_percent': failure_rate,
        'mttr_minutes': mttr,
        'governance_gate': governance.get('gate_status', 'UNKNOWN'),
        'critical_workflows': critical_workflows[:10],
        'recommendations': [
            'Priorizar workflows com maior taxa de falha.',
            'Reduzir MTTR operacional.',
            'Monitorar degradacao gradual de score operacional.'
        ],
        'blocked_actions': [
            'auto_merge',
            'deploy_without_review',
            'auto_remediation_without_evidence'
        ]
    }


def render_markdown(report: dict) -> str:
    lines = [
        '# Operational Risk Engine',
        '',
        f"Atualizado em UTC: `{report['generated_at_utc']}`",
        '',
        f"- Risk score: `{report['risk_score']}`",
        f"- Risk level: `{report['risk_level']}`",
        f"- Trend: `{report['trend_direction']}`",
        f"- Failure rate: `{report['failure_rate_percent']}%`",
        f"- MTTR: `{report['mttr_minutes']}`",
        f"- Governance gate: `{report['governance_gate']}`",
        '',
        '## Critical workflows',
        '',
        '| Workflow | Failure Rate |',
        '|---|---:|'
    ]

    for item in report['critical_workflows']:
        lines.append(
            f"| {item.get('workflow')} | {item.get('failure_rate_percent')}% |"
        )

    lines.extend([
        '',
        '## Recommendations',
        ''
    ])

    lines.extend([f"- {item}" for item in report['recommendations']])
    lines.append('')
    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description='ReqSys Operational Risk Engine')
    parser.add_argument('--history', type=Path, default=Path('artifacts/operational-history/operational-history.json'))
    parser.add_argument('--governance', type=Path, default=Path('artifacts/operational-governance-gate/operational-governance-gate.json'))
    parser.add_argument('--out-dir', type=Path, default=Path('artifacts/operational-risk-engine'))
    args = parser.parse_args()

    history = load_json(args.history, [])
    governance = load_json(args.governance, {})

    report = calculate_risk(history, governance)

    args.out_dir.mkdir(parents=True, exist_ok=True)

    (args.out_dir / 'operational-risk-engine.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )

    (args.out_dir / 'operational-risk-engine.md').write_text(
        render_markdown(report),
        encoding='utf-8'
    )

    print(render_markdown(report))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
