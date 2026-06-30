#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / 'docs/contracts/runtime-operational-contract-v1.json'

REQUIRED_FIELDS = {
    'runtime_score',
    'maturity_percent',
    'operational_risk',
    'readiness_status',
}


def fail(message: str) -> None:
    raise AssertionError(message)


def main() -> int:
    try:
        payload = json.loads(CONTRACT_PATH.read_text(encoding='utf-8'))

        if payload.get('artifact') != 'runtime-operational-contract':
            fail('invalid artifact')

        canonical_fields = payload.get('canonical_fields') or {}
        missing = REQUIRED_FIELDS - set(canonical_fields)

        if missing:
            fail(f'missing canonical fields: {sorted(missing)}')

        runtime_score = canonical_fields['runtime_score']
        if runtime_score.get('range') != [0, 100]:
            fail('runtime_score range must be [0, 100]')

        guardrails = payload.get('governance_guardrails') or []
        if len(guardrails) < 3:
            fail('minimum guardrails not satisfied')

        print(json.dumps({
            'status': 'passed',
            'validated': 'runtime_operational_contract'
        }, ensure_ascii=False))
        return 0

    except Exception as exc:
        print(json.dumps({
            'status': 'failed',
            'error': str(exc)
        }, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
