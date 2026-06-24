#!/usr/bin/env python3
import json
from datetime import datetime

TRANSIENT_ERRORS = [
    'timed out',
    'rate limit',
    'runner unavailable',
    'network',
    'cancelled'
]

BLOCKED_ERRORS = [
    'resource not accessible by integration',
    'secret',
    'permission',
    'branch protection',
    'merge conflict'
]


def classify_failure(message: str) -> str:
    msg = message.lower()
    if any(x in msg for x in BLOCKED_ERRORS):
        return 'manual-review'
    if any(x in msg for x in TRANSIENT_ERRORS):
        return 'safe-rerun'
    return 'unknown'


if __name__ == '__main__':
    sample = {
        'timestamp_utc': datetime.utcnow().isoformat(),
        'status': 'operational',
        'decision_engine': 'workflow-auto-remediation-runtime'
    }
    with open('workflow-runtime-health.json', 'w', encoding='utf-8') as fp:
        json.dump(sample, fp, indent=2)
    print(json.dumps(sample, indent=2))