#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CARD_ID = 'executive-final-sync-history-public-smoke-trend'
CONTRACT_KEY = 'executive_final_sync_history_public_smoke_trend'


def fetch_text(url: str, timeout: float = 15.0) -> str:
    request = urllib.request.Request(url, headers={'User-Agent': 'ReqSys-Final-Sync-Trend-Smoke/1.0'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode('utf-8')


def smoke(base_url: str, environment: str, timeout: float = 15.0) -> dict[str, Any]:
    base = base_url.rstrip('/')
    dashboard_url = f'{base}/'
    contract_url = f'{base}/data/runtime-executive-index.json'
    errors: list[str] = []

    try:
        html = fetch_text(dashboard_url, timeout)
    except (OSError, urllib.error.URLError, UnicodeDecodeError) as exc:
        html = ''
        errors.append(f'dashboard_unavailable: {exc}')

    try:
        contract = json.loads(fetch_text(contract_url, timeout))
    except (OSError, urllib.error.URLError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        contract = {}
        errors.append(f'contract_unavailable: {exc}')

    card = ((contract.get('cards') or {}).get(CONTRACT_KEY) or {}) if isinstance(contract, dict) else {}
    checks = {
        'dashboard_card_present': f'id="{CARD_ID}"' in html,
        'report_only': 'data-mode="report-only"' in html and card.get('mode') == 'report-only',
        'production_blocker_disabled': 'data-production-blocker="false"' in html and card.get('production_blocker') is False,
        'human_approval_required': card.get('human_approval_required') is True,
        'contract_card_present': bool(card),
    }
    errors.extend(name for name, passed in checks.items() if not passed)

    return {
        'schema_version': '1.0.0',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'environment': environment,
        'base_url': base,
        'status': 'passed' if not errors else 'failed',
        'decision': 'SYNCHRONIZED' if not errors else 'BLOCKED',
        'resolved_urls': {'dashboard': dashboard_url, 'contract': contract_url},
        'checks': checks,
        'card': {
            'status': card.get('status'),
            'environment_coverage': card.get('environment_coverage'),
            'samples': card.get('samples'),
            'pass_rate': card.get('pass_rate'),
            'minimum_stable_sequence': card.get('minimum_stable_sequence'),
            'eligible_for_human_review': card.get('eligible_for_human_review'),
        },
        'errors': errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Smoke público da tendência final sincronizada')
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--environment', required=True)
    parser.add_argument('--timeout', type=float, default=15.0)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    evidence = smoke(args.base_url, args.environment, args.timeout)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(evidence, ensure_ascii=False))
    return 0 if evidence['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
