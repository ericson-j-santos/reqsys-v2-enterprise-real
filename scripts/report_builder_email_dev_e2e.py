#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

RECIPIENT = 'ericson.takay@gmail.com'
CONFIRM = 'SEND-REPORT-BUILDER-EMAIL-DEV'


class E2EError(RuntimeError):
    pass


def request_json(url: str, token: str, payload: dict) -> tuple[int, dict]:
    request = Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        method='POST',
        headers={'Content-Type': 'application/json', 'X-Service-Token': token},
    )
    try:
        with urlopen(request, timeout=45) as response:
            raw = response.read().decode('utf-8')
            return response.status, json.loads(raw) if raw else {}
    except HTTPError as exc:
        return exc.code, {}
    except URLError as exc:
        raise E2EError(f'network_error:{type(exc.reason).__name__}') from None


def endpoint(api_base: str) -> str:
    root = api_base.rstrip('/')
    if root.endswith('/api'):
        return root + '/v1/report-builder/reports/generate-and-email'
    return root + '/api/v1/report-builder/reports/generate-and-email'


def execute(*, api_base: str, token: str, recipient: str, confirm: str) -> dict:
    if recipient.casefold() != RECIPIENT.casefold():
        raise E2EError('recipient_not_allowlisted')
    if confirm != CONFIRM:
        raise E2EError('explicit_confirmation_missing')
    if not token.strip():
        raise E2EError('service_token_missing')

    base_payload = {
        'report': {
            'report_name': 'ReportBuilderDeliveryProof',
            'display_name': 'Report Builder - Prova DEV',
            'description': 'Prova governada de aceite do provedor; entrega depende de readback.',
            'target_environment': 'dev',
            'query': "SELECT 'Report Builder' AS Componente, 'DEV' AS Ambiente",
            'fields': [
                {'name': 'Componente', 'title': 'Componente', 'data_type': 'String'},
                {'name': 'Ambiente', 'title': 'Ambiente', 'data_type': 'String'},
            ],
            'dry_run': True,
        },
        'recipients': [RECIPIENT],
        'subject': '[ReqSys DEV] Prova governada Report Builder',
        'body': 'Aceite do provedor não confirma entrega. Verifique esta mensagem na caixa destino.',
    }

    dry_status, dry_response = request_json(endpoint(api_base), token, {**base_payload, 'dry_run': True})
    dry_data = dry_response.get('data') or {}
    if dry_status != 200 or dry_data.get('status') != 'planned':
        raise E2EError(f'dry_run_failed:http_{dry_status}')

    send_status, send_response = request_json(endpoint(api_base), token, {**base_payload, 'dry_run': False})
    send_data = send_response.get('data') or {}
    delivery = send_data.get('delivery') or {}
    if send_status != 200 or send_data.get('status') != 'accepted_by_provider':
        raise E2EError(f'provider_acceptance_failed:http_{send_status}')
    if delivery.get('provider_accepted') is not True or delivery.get('recipient_delivery_confirmed') is not False:
        raise E2EError('delivery_state_invalid')

    return {
        'schema_version': '1.0.0',
        'status': 'accepted_pending_recipient_readback',
        'environment': 'dev',
        'recipient': RECIPIENT,
        'dry_run_verified': True,
        'provider': delivery.get('provider'),
        'provider_accepted': True,
        'recipient_delivery_confirmed': False,
        'recipient_delivery_evidence': delivery.get('recipient_delivery_evidence'),
        'correlation_id': send_data.get('correlation_id'),
        'definition_sha256': (send_data.get('report') or {}).get('definition_sha256'),
        'secret_value_exposed': False,
        'production_touched': False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--api-base', required=True)
    parser.add_argument('--recipient', required=True)
    parser.add_argument('--confirm', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    token = os.getenv('REQSYS_REPORT_BUILDER_SERVICE_TOKEN', '')
    try:
        evidence = execute(api_base=args.api_base, token=token, recipient=args.recipient, confirm=args.confirm)
    except E2EError as exc:
        evidence = {'schema_version': '1.0.0', 'status': 'blocked', 'reason': str(exc), 'secret_value_exposed': False, 'production_touched': False}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return 4
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
