#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SCOPE = 'teams_gateway:ai_conversations'
LABEL = 'pc24x7-teams-dev'
DEFAULT_SECRET_NAME = 'reqsys-pc24x7-teams-service-token'
DEFAULT_API = 'https://reqsys-api-dev.fly.dev'


class BootstrapError(RuntimeError):
    pass


@dataclass(frozen=True)
class BootstrapResult:
    status: str
    environment: str
    secret_name: str
    scope: str
    token_created: bool
    existing_token_reused: bool
    readiness_http_status: int | None
    secret_value_exposed: bool = False


def request_json(method: str, url: str, *, headers: dict[str, str], body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode('utf-8') if body is not None else None
    req = Request(url, data=data, method=method, headers=headers)
    if data is not None:
        req.add_header('Content-Type', 'application/json')
    try:
        with urlopen(req, timeout=30) as response:  # noqa: S310 - URLs are controlled configuration.
            raw = response.read().decode('utf-8')
            return response.status, json.loads(raw) if raw else {}
    except HTTPError as exc:
        return exc.code, {}
    except URLError as exc:
        raise BootstrapError(f'network_error:{type(exc.reason).__name__}') from None


def validate_service_token(api_base: str, token: str) -> int:
    status, _ = request_json(
        'GET',
        api_base.rstrip('/') + '/v1/teams-gateway/ai-conversations/readiness',
        headers={'X-Service-Token': token, 'X-Correlation-Id': 'pc24x7-token-bootstrap-readiness'},
    )
    return status


def read_admin_jwt(cofre_base: str, vault_token: str, *, environment: str = 'dev') -> str:
    status, payload = request_json(
        'GET',
        cofre_base.rstrip('/') + f'/v1/cofre/segredos/human_admin_jwt:{environment}',
        headers={'X-Vault-Token': vault_token},
    )
    if status != 200:
        raise BootstrapError(f'admin_jwt_unavailable:http_{status}')
    try:
        stored = json.loads(payload['data']['value'])
        token = str(stored['token']).strip()
        exp = int(stored['exp'])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise BootstrapError('admin_jwt_payload_invalid') from exc
    if not token or exp <= int(time.time()) + 120:
        raise BootstrapError('admin_jwt_expired_or_too_close_to_expiry')
    return token


def mint_service_token(api_base: str, admin_jwt: str, *, expires_in_days: int = 90) -> str:
    status, payload = request_json(
        'POST',
        api_base.rstrip('/') + '/v1/admin/service-tokens',
        headers={
            'Authorization': f'Bearer {admin_jwt}',
            'X-Correlation-Id': 'pc24x7-token-bootstrap-mint',
        },
        body={'label': LABEL, 'scopes': [SCOPE], 'expires_in_days': expires_in_days},
    )
    if status not in (200, 201):
        raise BootstrapError(f'service_token_mint_failed:http_{status}')
    try:
        token = str(payload['data']['token']).strip()
    except (KeyError, TypeError):
        raise BootstrapError('service_token_response_without_token') from None
    if not token:
        raise BootstrapError('service_token_response_empty_token')
    return token


def keyvault_client(vault_name: str):
    try:
        from azure.identity import AzureCliCredential
        from azure.keyvault.secrets import SecretClient
    except ImportError as exc:
        raise BootstrapError('azure_sdk_not_installed') from exc
    return SecretClient(vault_url=f'https://{vault_name}.vault.azure.net', credential=AzureCliCredential())


def bootstrap(
    *,
    api_base: str,
    cofre_base: str,
    vault_token: str,
    vault_name: str,
    secret_name: str,
    allow_provision: bool = True,
) -> BootstrapResult:
    client = keyvault_client(vault_name)
    existing = None
    try:
        existing = client.get_secret(secret_name).value
    except Exception as exc:  # Azure SDK raises typed exceptions; absence is handled by mint path.
        if exc.__class__.__name__ not in {'ResourceNotFoundError', 'SecretNotFound'}:
            raise BootstrapError(f'keyvault_read_failed:{exc.__class__.__name__}') from None

    if existing:
        readiness = validate_service_token(api_base, str(existing))
        if readiness == 200:
            return BootstrapResult(
                status='ready', environment='dev', secret_name=secret_name, scope=SCOPE,
                token_created=False, existing_token_reused=True, readiness_http_status=200,
            )
        if not allow_provision:
            raise BootstrapError(f'existing_service_token_readiness_failed:http_{readiness}')
    elif not allow_provision:
        raise BootstrapError('service_token_missing_provisioning_disabled')

    admin_jwt = read_admin_jwt(cofre_base, vault_token, environment='dev')
    new_token = mint_service_token(api_base, admin_jwt)
    client.set_secret(
        secret_name,
        new_token,
        tags={'environment': 'dev', 'consumer': 'pc24x7-teams-worker', 'scope': SCOPE, 'source': 'reqsys-service-token'},
    )
    readiness = validate_service_token(api_base, new_token)
    if readiness != 200:
        raise BootstrapError(f'new_service_token_readiness_failed:http_{readiness}')
    return BootstrapResult(
        status='ready', environment='dev', secret_name=secret_name, scope=SCOPE,
        token_created=True, existing_token_reused=False, readiness_http_status=readiness,
    )


def main() -> int:
    api_base = os.getenv('REQSYS_API_BASE_URL', DEFAULT_API).strip() or DEFAULT_API
    cofre_base = os.getenv('COFRE_API_URL', api_base).strip() or api_base
    vault_token = os.getenv('VAULT_API_TOKEN', '').strip()
    vault_name = os.getenv('REQSYS_KEY_VAULT_NAME', '').strip()
    secret_name = os.getenv('PC24X7_TEAMS_SERVICE_TOKEN_SECRET', DEFAULT_SECRET_NAME).strip() or DEFAULT_SECRET_NAME
    allow_provision = os.getenv('PC24X7_TEAMS_ALLOW_PROVISION', 'true').strip().lower() in {'1', 'true', 'yes', 'on'}
    if not vault_token:
        print(json.dumps({'status': 'blocked', 'reason': 'VAULT_API_TOKEN_missing', 'secret_value_exposed': False}))
        return 4
    if not vault_name:
        print(json.dumps({'status': 'blocked', 'reason': 'REQSYS_KEY_VAULT_NAME_missing', 'secret_value_exposed': False}))
        return 4
    try:
        result = bootstrap(
            api_base=api_base, cofre_base=cofre_base, vault_token=vault_token,
            vault_name=vault_name, secret_name=secret_name, allow_provision=allow_provision,
        )
    except BootstrapError as exc:
        print(json.dumps({'status': 'blocked', 'reason': str(exc), 'secret_value_exposed': False}))
        return 4
    print(json.dumps(asdict(result), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
