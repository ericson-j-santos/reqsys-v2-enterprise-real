#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

CARD_ID = 'empty-state-recovery-advisory'


def build_advisory(indicator: dict[str, Any]) -> dict[str, Any]:
    contexts = indicator.get('contexts', {}) if isinstance(indicator, dict) else {}
    recovery = indicator.get('recovery_by_context', {}) if isinstance(indicator, dict) else {}
    ranked = []
    for context, views in contexts.items():
        rate = float(recovery.get(context, 0) or 0)
        ranked.append({
            'context': str(context)[:80],
            'views': int(views or 0),
            'recovery_rate': rate,
            'priority': 'P1' if rate < 20 else 'P2' if rate < 40 else 'P3',
            'recommendation': 'Revisar filtros, texto orientativo e ação principal.',
        })
    ranked.sort(key=lambda item: (item['recovery_rate'], -item['views'], item['context']))
    return {
        'id': CARD_ID,
        'title': 'Advisory de recuperação de estados vazios',
        'status': 'UX_EMPTY_STATE_ADVISORY',
        'mode': 'advisory',
        'production_blocker': False,
        'human_approval_required': True,
        'priorities': ranked[:10],
        'evidence_complete': bool(ranked),
    }


def publish_ops_dashboard(dashboard: dict[str, Any], advisory: dict[str, Any]) -> dict[str, Any]:
    output = deepcopy(dashboard) if isinstance(dashboard, dict) else {}
    cards = output.get('cards', [])
    cards = cards if isinstance(cards, list) else []
    output['cards'] = [
        card for card in cards
        if not (isinstance(card, dict) and card.get('id') == CARD_ID)
    ] + [advisory]
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--indicator', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--dashboard', type=Path)
    parser.add_argument('--dashboard-output', type=Path)
    args = parser.parse_args()

    indicator = json.loads(args.indicator.read_text(encoding='utf-8'))
    advisory = build_advisory(indicator)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(advisory, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    if args.dashboard and args.dashboard_output:
        dashboard = json.loads(args.dashboard.read_text(encoding='utf-8'))
        published = publish_ops_dashboard(dashboard, advisory)
        args.dashboard_output.parent.mkdir(parents=True, exist_ok=True)
        args.dashboard_output.write_text(json.dumps(published, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
