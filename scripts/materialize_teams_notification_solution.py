#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'backend'
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.teams_notification_solution_factory import gerar_teams_notification_solution


def materialize(output_dir: Path, *, target_environment: str, dry_run: bool) -> dict[str, object]:
    solution = gerar_teams_notification_solution(
        target_environment=target_environment,
        dry_run=dry_run,
    )
    package = solution['package']
    output_dir.mkdir(parents=True, exist_ok=True)

    zip_path = output_dir / package['zip_filename']
    zip_path.write_bytes(base64.b64decode(package['zip_base64']))

    manifest = {
        'profile': 'teams_notification_v2',
        'solution_name': solution['solution']['unique_name'],
        'flow_name': solution['flow']['name'],
        'version': solution['flow']['version'],
        'target_environment': target_environment,
        'correlation_id': solution['correlation_id'],
        'sha256': package['sha256'],
        'zip_filename': package['zip_filename'],
        'files': package['files'],
        'import_guardrails': {
            'dev_only_without_approval': True,
            'flow_state_after_import': solution['flow']['state'],
            'requires_connection_reference': True,
            'requires_environment_variables': True,
        },
    }
    manifest_path = output_dir / 'materialization-manifest.json'
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'zip_path': str(zip_path), 'manifest_path': str(manifest_path), **manifest}


def main() -> int:
    parser = argparse.ArgumentParser(description='Materializa a solution ReqSys Teams Notifications v2.')
    parser.add_argument('--output-dir', default='artifacts/lowcode-solution-factory/teams-notifications-v2')
    parser.add_argument('--target-environment', default='dev')
    parser.add_argument('--ready-for-import', action='store_true')
    args = parser.parse_args()

    if args.target_environment.lower() != 'dev' and args.ready_for_import:
        parser.error('Materializacao pronta para importacao e permitida somente para DEV neste incremento.')

    result = materialize(
        ROOT / args.output_dir,
        target_environment=args.target_environment,
        dry_run=not args.ready_for_import,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
