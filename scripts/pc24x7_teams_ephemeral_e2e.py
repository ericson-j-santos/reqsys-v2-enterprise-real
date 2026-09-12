#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import tempfile
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pc24x7_teams_queue as queue

API_DEFAULT = 'https://reqsys-api-dev.fly.dev'
ADMIN_EMAIL_DEFAULT = 'ericsonjosedossantos@tieri659.onmicrosoft.com'
SCOPE = 'teams_gateway:ai_conversations'
TOKEN_TTL_DAYS = 1
PRODUCTION_ENVIRONMENTS = {'prod', 'production', 'producao', 'produção'}


class EphemeralE2EError(RuntimeError):
    pass


def request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    body: dict | None = None,
) -> tuple[int, dict]:
    data = json.dumps(body).encode('utf-8') if body is not None else None
    request = Request(url, data=data, method=method, headers=headers)
    if data is not None:
        request.add_header('Content-Type', 'application/json')
    try:
        with urlopen(request, timeout=90) as response:  # noqa: S310
            raw = response.read().decode('utf-8')
            return response.status, json.loads(raw) if raw else {}
    except HTTPError as exc:
        return exc.code, {}
    except URLError as exc:
        raise EphemeralE2EError(f'network_error:{type(exc.reason).__name__}') from None


def _data(payload: dict) -> dict:
    data = payload.get('data') if isinstance(payload, dict) else None
    return data if isinstance(data, dict) else payload if isinstance(payload, dict) else {}


def validate_admin_jwt(api_base: str, admin_jwt: str, correlation_id: str) -> bool:
    if not admin_jwt.strip():
        return False
    status, payload = request_json(
        'GET',
        api_base.rstrip('/') + '/v1/auth/session',
        headers={
            'Authorization': f'Bearer {admin_jwt}',
            'X-Correlation-Id': correlation_id + '-admin-check',
        },
    )
    return status == 200 and str(_data(payload).get('papel') or '').lower() == 'admin'


def mint_dev_admin_jwt(api_base: str, correlation_id: str, admin_email: str) -> str:
    config_status, config_payload = request_json(
        'GET',
        api_base.rstrip('/') + '/v1/auth/config',
        headers={'X-Correlation-Id': correlation_id + '-auth-config'},
    )
    if config_status != 200:
        raise EphemeralE2EError(f'admin_auth_config_failed:http_{config_status}')

    config = _data(config_payload)
    environment = str(config.get('environment') or '').strip().lower()
    if environment in PRODUCTION_ENVIRONMENTS:
        raise EphemeralE2EError('admin_auth_refused:production')
    if config.get('demo_login_enabled') is not True:
        raise EphemeralE2EError('admin_auth_unavailable:demo_login_disabled')

    login_status, login_payload = request_json(
        'POST',
        api_base.rstrip('/') + '/v1/auth/login',
        headers={'X-Correlation-Id': correlation_id + '-dev-login'},
        body={'email': admin_email},
    )
    if login_status != 200:
        raise EphemeralE2EError(f'admin_auth_dev_login_failed:http_{login_status}')

    login = _data(login_payload)
    usuario = login.get('usuario') if isinstance(login.get('usuario'), dict) else {}
    if str(usuario.get('papel') or '').lower() != 'admin':
        raise EphemeralE2EError('admin_auth_dev_login_not_admin')
    token = str(login.get('access_token') or '').strip()
    if not token:
        raise EphemeralE2EError('admin_auth_dev_login_token_missing')
    return token


def resolve_admin_jwt(
    api_base: str,
    configured_admin_jwt: str,
    correlation_id: str,
    admin_email: str,
) -> tuple[str, str, bool]:
    if validate_admin_jwt(api_base, configured_admin_jwt, correlation_id):
        return configured_admin_jwt, 'environment_secret_valid', False
    fresh = mint_dev_admin_jwt(api_base, correlation_id, admin_email)
    return fresh, 'dev_demo_ephemeral', True


def mint_ephemeral_token(api_base: str, admin_jwt: str, correlation_id: str) -> tuple[int, str]:
    status, payload = request_json(
        'POST',
        api_base.rstrip('/') + '/v1/admin/service-tokens',
        headers={
            'Authorization': f'Bearer {admin_jwt}',
            'X-Correlation-Id': correlation_id + '-mint',
        },
        body={
            'label': f'pc24x7-teams-dev-e2e-{correlation_id[-12:]}',
            'scopes': [SCOPE],
            'expires_in_days': TOKEN_TTL_DAYS,
        },
    )
    if status not in (200, 201):
        raise EphemeralE2EError(f'service_token_mint_failed:http_{status}')
    data = _data(payload)
    try:
        token_id = int(data['id'])
        token = str(data['token']).strip()
    except (KeyError, TypeError, ValueError) as exc:
        raise EphemeralE2EError('service_token_response_invalid') from exc
    if not token:
        raise EphemeralE2EError('service_token_response_empty')
    return token_id, token


def revoke_ephemeral_token(api_base: str, admin_jwt: str, token_id: int, correlation_id: str) -> bool:
    status, payload = request_json(
        'DELETE',
        api_base.rstrip('/') + f'/v1/admin/service-tokens/{token_id}',
        headers={
            'Authorization': f'Bearer {admin_jwt}',
            'X-Correlation-Id': correlation_id + '-revoke',
        },
    )
    return status == 200 and _data(payload).get('revogado') is True


def check_readiness(api_base: str, token: str, correlation_id: str) -> tuple[int, dict]:
    status, payload = request_json(
        'GET',
        api_base.rstrip('/') + '/v1/teams-gateway/ai-conversations/readiness',
        headers={
            'X-Service-Token': token,
            'X-Correlation-Id': correlation_id + '-readiness',
        },
    )
    data = _data(payload)
    blockers = data.get('bloqueios') if isinstance(data.get('bloqueios'), list) else []
    blocker_codes = sorted(
        str(item.get('codigo'))
        for item in blockers
        if isinstance(item, dict) and item.get('codigo')
    )
    summary = {
        'http_status': status,
        'schema_version': data.get('schema_version'),
        'status': data.get('status'),
        'ready': data.get('ready') is True,
        'blocker_codes': blocker_codes,
        'conversation_references': data.get('conversation_references'),
        'secret_value_exposed': False,
    }
    return status, summary


def execute_e2e(
    *,
    api_base: str,
    admin_jwt: str,
    correlation_id: str,
    provider: str,
    model: str,
    admin_email: str = ADMIN_EMAIL_DEFAULT,
) -> dict:
    evidence: dict = {
        'schema_version': '1.1.0',
        'status': 'blocked',
        'environment': 'dev',
        'correlation_id': correlation_id,
        'scope': SCOPE,
        'admin_auth_source': None,
        'admin_auth_recovered': False,
        'token_created': False,
        'token_revoked': False,
        'readiness': None,
        'delivery': None,
        'queue_idempotency_proven': False,
        'error': None,
        'secret_value_exposed': False,
        'production_touched': False,
        'test_touched': False,
    }
    token_id: int | None = None
    token = ''
    effective_admin_jwt = ''
    try:
        effective_admin_jwt, auth_source, recovered = resolve_admin_jwt(
            api_base,
            admin_jwt,
            correlation_id,
            admin_email,
        )
        evidence['admin_auth_source'] = auth_source
        evidence['admin_auth_recovered'] = recovered

        token_id, token = mint_ephemeral_token(api_base, effective_admin_jwt, correlation_id)
        evidence['token_created'] = True

        with tempfile.TemporaryDirectory(prefix='reqsys-pc24x7-e2e-') as tmp:
            root = Path(tmp) / 'queue'
            token_file = Path(tmp) / 'service-token'
            token_file.write_text(token, encoding='utf-8')
            try:
                token_file.chmod(0o600)
            except OSError:
                pass

            readiness_status, readiness = check_readiness(api_base, token, correlation_id)
            evidence['readiness'] = readiness
            if readiness_status != 200 or readiness.get('ready') is not True:
                raise EphemeralE2EError('readiness_not_ready')

            job = queue.build_job(
                provider=provider,
                model=model,
                mensagem=f'ReqSys PC24x7 DEV E2E {correlation_id}',
                titulo='ReqSys PC24x7 Teams DEV — aceite efêmero',
                correlation_id=correlation_id,
            )
            first_path = queue.enqueue(root, job)
            delivery = queue.process_one(root, api_base, token_file)
            evidence['delivery'] = delivery
            if not delivery or delivery.get('status') != 'done':
                raise EphemeralE2EError('teams_delivery_not_done')
            if delivery.get('teams_delivered') is not True or delivery.get('teams_channel') != 'bot':
                raise EphemeralE2EError('teams_delivery_not_confirmed')
            if not delivery.get('conversation_id'):
                raise EphemeralE2EError('conversation_id_missing')

            duplicate_path = queue.enqueue(root, job)
            second_delivery = queue.process_one(root, api_base, token_file)
            done_path = root / 'done' / first_path.name
            evidence['queue_idempotency_proven'] = duplicate_path == done_path and second_delivery is None
            if evidence['queue_idempotency_proven'] is not True:
                raise EphemeralE2EError('queue_idempotency_not_proven')

            evidence['status'] = 'done'
    except EphemeralE2EError as exc:
        evidence['error'] = str(exc)
    except Exception as exc:  # fail closed without serializing sensitive values
        evidence['error'] = f'unexpected:{type(exc).__name__}'
    finally:
        token = ''
        if token_id is not None:
            try:
                evidence['token_revoked'] = revoke_ephemeral_token(
                    api_base, effective_admin_jwt, token_id, correlation_id
                )
            except Exception as exc:
                evidence['token_revoked'] = False
                if evidence['error'] is None:
                    evidence['error'] = f'revoke_failed:{type(exc).__name__}'
        effective_admin_jwt = ''
        if token_id is not None and evidence['token_revoked'] is not True:
            evidence['status'] = 'blocked'
            if evidence['error'] is None:
                evidence['error'] = 'token_revoke_not_confirmed'
    return evidence


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='PC24x7 Teams DEV ephemeral E2E')
    parser.add_argument('--api-base', default=os.getenv('REQSYS_API_BASE_URL', API_DEFAULT))
    parser.add_argument('--provider', default=os.getenv('PC24X7_TEAMS_E2E_PROVIDER', 'gemini'))
    parser.add_argument('--model', default=os.getenv('PC24X7_TEAMS_E2E_MODEL', 'gemini-2.5-flash'))
    parser.add_argument('--admin-email', default=os.getenv('PC24X7_TEAMS_E2E_ADMIN_EMAIL', ADMIN_EMAIL_DEFAULT))
    parser.add_argument('--correlation-id', default=os.getenv('PC24X7_TEAMS_E2E_CORRELATION_ID'))
    parser.add_argument('--evidence-path', default='artifacts/pc24x7-teams-ephemeral-e2e/evidence.json')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    correlation_id = args.correlation_id or f'pc24x7-ephemeral-{uuid.uuid4()}'
    evidence = execute_e2e(
        api_base=args.api_base,
        admin_jwt=os.getenv('COFRE_ADMIN_JWT', ''),
        correlation_id=correlation_id,
        provider=args.provider,
        model=args.model,
        admin_email=args.admin_email,
    )
    output = Path(args.evidence_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))
    return 0 if evidence['status'] == 'done' and evidence['token_revoked'] is True else 4


if __name__ == '__main__':
    raise SystemExit(main())
