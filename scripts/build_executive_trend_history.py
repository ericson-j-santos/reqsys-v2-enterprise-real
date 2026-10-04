#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

WINDOW = 10


def load_json(path: str | Path, fallback: Any) -> Any:
    file_path = Path(path)
    if not file_path.exists():
        return fallback
    return json.loads(file_path.read_text(encoding='utf-8'))


def clamp(value: float, minimum: float = 0, maximum: float = 100) -> float:
    return max(minimum, min(maximum, value))


def slope(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return round((values[-1] - values[0]) / max(len(values) - 1, 1), 2)


def classify_trend(delta: float) -> str:
    if delta >= 2:
        return 'improving'
    if delta <= -2:
        return 'degrading'
    return 'stable'


def freeze_recommendation(executive_score: float, readiness: float, mergeability: float) -> str:
    if executive_score < 45 or readiness < 50:
        return 'freeze_expansion'
    if mergeability < 60:
        return 'stabilize_merge_flow'
    if executive_score >= 80 and readiness >= 80 and mergeability >= 80:
        return 'safe_to_expand'
    return 'governed_expansion'


def build_snapshot(runtime: dict[str, Any], governance: dict[str, Any]) -> dict[str, Any]:
    runtime_summary = runtime.get('summary') or {}
    runtime_cards = runtime.get('cards') or {}
    readiness = runtime_cards.get('readiness') or {}
    merge = runtime_cards.get('merge_intelligence') or {}

    executive_score = float(runtime_summary.get('executive_score', 0) or 0)
    readiness_score = float(readiness.get('readiness_percent', 0) or 0)
    mergeability_score = float(merge.get('mergeability_score', 0) or 0)

    return {
        'timestamp_epoch': int(time.time()),
        'executive_score': executive_score,
        'readiness_score': readiness_score,
        'mergeability_score': mergeability_score,
        'strategic_score': float((governance.get('summary') or {}).get('strategic_score', 0) or 0),
        'next_bottleneck': (governance.get('summary') or {}).get('next_bottleneck', 'unknown'),
        'recommended_action': (governance.get('summary') or {}).get('recommended_action', 'unknown'),
        'freeze_recommendation': freeze_recommendation(executive_score, readiness_score, mergeability_score),
    }


def build_history(history: list[dict[str, Any]], snapshot: dict[str, Any]) -> dict[str, Any]:
    entries = (history + [snapshot])[-WINDOW:]

    executive_values = [float(item.get('executive_score', 0)) for item in entries]
    readiness_values = [float(item.get('readiness_score', 0)) for item in entries]
    mergeability_values = [float(item.get('mergeability_score', 0)) for item in entries]

    executive_slope = slope(executive_values)
    readiness_slope = slope(readiness_values)
    mergeability_slope = slope(mergeability_values)

    operational_decay = clamp(
        100 - ((executive_values[-1] + readiness_values[-1] + mergeability_values[-1]) / 3)
    )

    return {
        'schema_version': '1.0.0',
        'window_size': WINDOW,
        'summary': {
            'entries': len(entries),
            'executive_trend': classify_trend(executive_slope),
            'readiness_trend': classify_trend(readiness_slope),
            'mergeability_trend': classify_trend(mergeability_slope),
            'executive_slope': executive_slope,
            'readiness_slope': readiness_slope,
            'mergeability_slope': mergeability_slope,
            'operational_decay_percent': round(operational_decay, 2),
            'latest_freeze_recommendation': snapshot['freeze_recommendation'],
            'latest_next_bottleneck': snapshot['next_bottleneck'],
        },
        'history': entries,
        'guardrails': [
            'offline_history_only',
            'no_predictive_ai_decision',
            'recommendation_does_not_override_ci',
            'governed_expansion_only',
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime-index', default='docs/ops-dashboard/data/runtime-executive-index.json')
    parser.add_argument('--strategic-index', default='docs/ops-dashboard/data/strategic-governance-index.json')
    parser.add_argument('--history', default='docs/ops-dashboard/data/executive-trend-history.json')
    args = parser.parse_args()

    runtime = load_json(args.runtime_index, {})
    governance = load_json(args.strategic_index, {})
    previous = load_json(args.history, {'history': []})

    snapshot = build_snapshot(runtime, governance)
    payload = build_history(previous.get('history') or [], snapshot)

    output = Path(args.history)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
