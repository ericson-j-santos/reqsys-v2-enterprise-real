#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


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
        'mode': 'advisory',
        'production_blocker': False,
        'human_approval_required': True,
        'priorities': ranked[:10],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--indicator', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    indicator = json.loads(args.indicator.read_text(encoding='utf-8'))
    advisory = build_advisory(indicator)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(advisory, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
