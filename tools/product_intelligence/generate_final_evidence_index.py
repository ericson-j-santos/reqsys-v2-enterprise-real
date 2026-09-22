#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REQUIRED_ARTIFACTS = [
    'product-intelligence-consolidated-governance-report.json',
    'product-intelligence-governance-closure-pack.json',
    'product-intelligence-governance-stabilization-gate.json',
    'product-intelligence-governance-stability-index.json',
    'product-intelligence-governance-drift-detector.json',
    'product-intelligence-continuous-governance-snapshot.json',
    'product-intelligence-executive-control-tower.json',
    'product-intelligence-release-governance-gate.json',
    'product-intelligence-release-evidence-pack.json',
]


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError(f'Invalid JSON object: {path}')
    return value


def main() -> int:
    report_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('reports/product-intelligence')
    report_dir.mkdir(parents=True, exist_ok=True)

    evidence = []
    missing = []
    for artifact in REQUIRED_ARTIFACTS:
        payload = load_json(report_dir / artifact)
        if not payload:
            missing.append(artifact)
        evidence.append({
            'artifact': artifact,
            'path': f'reports/product-intelligence/{artifact}',
            'available': bool(payload),
        })

    coverage = round(((len(REQUIRED_ARTIFACTS) - len(missing)) / len(REQUIRED_ARTIFACTS)) * 100, 2)
    readiness_state = 'FINAL_EVIDENCE_INDEX_COMPLETE' if not missing else 'FINAL_EVIDENCE_INDEX_INCOMPLETE'

    payload = {
        'schema_version': '1.0.0',
        'name': 'product-intelligence-final-evidence-index',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'mode': 'review_only',
        'readiness_state': readiness_state,
        'evidence_coverage_percent': coverage,
        'confidence_percent': 90 if coverage == 100.0 else 70,
        'risk_percent': 5 if coverage == 100.0 else 20,
        'required_artifact_count': len(REQUIRED_ARTIFACTS),
        'artifact_count': len(REQUIRED_ARTIFACTS) - len(missing),
        'missing_artifacts': missing,
        'evidence': evidence,
        'human_review_required': True,
    }

    (report_dir / 'product-intelligence-final-evidence-index.json').write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )

    rows = '\n'.join(
        f"| `{item['artifact']}` | {item['available']} | `{item['path']}` |"
        for item in evidence
    )
    markdown = f'''# Product Intelligence Final Evidence Index

| Field | Value |
|---|---:|
| Readiness state | {readiness_state} |
| Evidence coverage | {coverage}% |
| Confidence | {payload['confidence_percent']}% |
| Risk | {payload['risk_percent']}% |
| Artifacts | {payload['artifact_count']} / {payload['required_artifact_count']} |

## Evidence map

| Artifact | Available | Path |
|---|---:|---|
{rows}

## Guardrail

Human governance review remains required before production decisions.
'''
    (report_dir / 'product-intelligence-final-evidence-index.md').write_text(markdown, encoding='utf-8')
    print(f"Final evidence index: {readiness_state} coverage={coverage}%")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
