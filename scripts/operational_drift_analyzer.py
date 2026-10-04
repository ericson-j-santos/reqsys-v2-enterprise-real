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


def avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


def classify_drift(delta_score: float, delta_failure: float, delta_risk: float) -> str:
    if delta_score <= -10 or delta_failure >= 20 or delta_risk >= 20:
        return 'CRITICO'
    if delta_score <= -5 or delta_failure >= 10 or delta_risk >= 10:
        return 'ALTO'
    if delta_score <= -2 or delta_failure >= 5 or delta_risk >= 5:
        return 'MEDIO'
    return 'BAIXO'


def analyze(history: list, risk: dict) -> dict:
    points = [item for item in history if isinstance(item, dict)]
    last = points[-1] if points else {}
    previous = points[-2] if len(points) >= 2 else {}

    last_score = float(last.get('hub_score') or 0)
    prev_score = float(previous.get('hub_score') or last_score)
    delta_score = round(last_score - prev_score, 2)

    last_failure = float(last.get('metrics', {}).get('overall_failure_rate_percent') or 0)
    prev_failure = float(previous.get('metrics', {}).get('overall_failure_rate_percent') or last_failure)
    delta_failure = round(last_failure - prev_failure, 2)

    current_risk = float(risk.get('risk_score') or 0)
    previous_risk = current_risk
    delta_risk = 0.0

    scores = [float(item.get('hub_score') or 0) for item in points[-10:]]
    failures = [float(item.get('metrics', {}).get('overall_failure_rate_percent') or 0) for item in points[-10:]]

    stability_index = round(max(0, min(100, avg(scores) - avg(failures))), 2)
    drift_level = classify_drift(delta_score, delta_failure, delta_risk)

    if delta_score < -3 or delta_failure > 5:
        forecast = 'DEGRADACAO_PROVAVEL'
    elif delta_score > 3 and delta_failure <= 0:
        forecast = 'MELHORA_PROVAVEL'
    else:
        forecast = 'ESTAVEL'

    return {
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'points_analyzed': len(points),
        'drift_level': drift_level,
        'delta_score': delta_score,
        'delta_failure_rate': delta_failure,
        'delta_risk': delta_risk,
        'current_risk_score': current_risk,
        'stability_index': stability_index,
        'forecast': forecast,
        'risk_acceleration': delta_risk,
        'recommendations': build_recommendations(drift_level, forecast),
        'blocked_actions': [
            'automatic_destructive_decision',
            'production_block_by_weak_heuristic',
            'auto_remediation_without_evidence'
        ]
    }


def build_recommendations(drift_level: str, forecast: str) -> list[str]:
    actions = []
    if drift_level in {'ALTO', 'CRITICO'}:
        actions.append('Priorizar estabilizacao antes de novos incrementos grandes.')
    if forecast == 'DEGRADACAO_PROVAVEL':
        actions.append('Investigar variacao negativa de score e aumento de taxa de falha.')
    actions.append('Acompanhar drift por pelo menos tres snapshots antes de automatizar bloqueios fortes.')
    return actions


def render_markdown(report: dict) -> str:
    lines = [
        '# Operational Drift Analyzer',
        '',
        f"Atualizado em UTC: `{report['generated_at_utc']}`",
        '',
        f"- Drift level: `{report['drift_level']}`",
        f"- Forecast: `{report['forecast']}`",
        f"- Stability index: `{report['stability_index']}`",
        f"- Delta score: `{report['delta_score']}`",
        f"- Delta failure rate: `{report['delta_failure_rate']}`",
        f"- Current risk score: `{report['current_risk_score']}`",
        '',
        '## Recommendations',
        ''
    ]
    lines.extend(f"- {item}" for item in report['recommendations'])
    lines.append('')
    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description='ReqSys Operational Drift Analyzer')
    parser.add_argument('--history', type=Path, default=Path('artifacts/operational-history/operational-history.json'))
    parser.add_argument('--risk', type=Path, default=Path('artifacts/operational-risk-engine/operational-risk-engine.json'))
    parser.add_argument('--out-dir', type=Path, default=Path('artifacts/operational-drift-analyzer'))
    args = parser.parse_args()

    history = load_json(args.history, [])
    risk = load_json(args.risk, {})
    report = analyze(history, risk)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / 'operational-drift-analyzer.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (args.out_dir / 'operational-drift-analyzer.md').write_text(render_markdown(report), encoding='utf-8')
    print(render_markdown(report))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
