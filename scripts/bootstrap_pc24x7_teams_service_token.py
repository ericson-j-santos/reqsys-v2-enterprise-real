#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SCOPE = os.getenv('REQSYS_SERVICE_TOKEN_SCOPE', 'teams_gateway:ai_conversations').strip() or 'teams_gateway:ai_conversations'
LABEL = os.getenv('REQSYS_SERVICE_TOKEN_LABEL', 'pc24x7-teams-dev').strip() or 'pc24x7-teams-dev'
DEFAULT_SECRET_NAME = os.getenv('REQSYS_SERVICE_TOKEN_SECRET_NAME', 'reqsys-pc24x7-teams-service-token').strip() or 'reqsys-pc24x7-teams-service-token'
VALIDATION_PATH = os.getenv('REQSYS_SERVICE_TOKEN_VALIDATION_PATH', '/v1/teams-gateway/ai-conversations/readiness').strip() or '/v1/teams-gateway/ai-conversations/readiness'
DEFAULT_API = ''
DEFAULT_LOCAL_COFRE_CONTAINER = 'wt-pc24x7-piloto-api-1'


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
        with urlopen(req, timeout=30) as response:  # noqa: S310
            raw = response.read().decode('utf-8')
            return response.status, json.loads(raw) if raw else {}
    except HTTPError as exc:
        return exc.code, {}
    except URLError as exc:
        raise BootstrapError(f'network_error:{type(exc.reason).__name__}') from None


def runtime_api_url(api_base: str, path: str) -> str:
    root = api_base.rstrip('/')
    if not path.startswith('/v1/'):
        raise BootstrapError('runtime_api_path_invalid')
    if root.endswith('/api'):
        return root + path
    return root + '/api' + path


def validate_service_token(api_base: str, token: str) -> int:
    status, _ = request_json('GET', runtime_api_url(api_base, VALIDATION_PATH), headers={'X-Service-Token': token, 'X-Correlation-Id': 'pc24x7-token-bootstrap-readiness'})
    return status


def read_admin_jwt(cofre_base: str, vault_token: str, *, environment: str = 'dev') -> str:
    status, payload = request_json('GET', runtime_api_url(cofre_base, f'/v1/cofre/segredos/human_admin_jwt:{environment}'), headers={'X-Vault-Token': vault_token})
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


def read_admin_jwt_from_local_runtime(container: str, *, environment: str = 'dev') -> str:
    """Lê o JWT somente do keyring persistente do runtime DEV no PC24x7.

    O valor trafega apenas pelo pipe local capturado pelo processo e nunca é
    incluído na evidência sanitizada. A identidade Compose impede apontar este
    bootstrap para outro container/ambiente.
    """
    if container != DEFAULT_LOCAL_COFRE_CONTAINER or environment != 'dev':
        raise BootstrapError('local_cofre_target_blocked')
    probe = (
        "import json\n"
        "from app.core.secrets import read_secret_from_vault\n"
        f"raw=read_secret_from_vault('human_admin_jwt:{environment}')\n"
        "print(raw or '')\n"
    )
    try:
        completed = subprocess.run(
            ['docker', 'exec', '-i', container, 'python', '-'],
            input=probe,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=30,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BootstrapError(f'local_cofre_read_failed:{type(exc).__name__}') from None
    if completed.returncode != 0:
        raise BootstrapError(f'local_cofre_read_failed:exit_{completed.returncode}')
    raw = completed.stdout.strip()
    if not raw:
        raise BootstrapError('admin_jwt_unavailable_local')
    try:
        stored = json.loads(raw)
        token = str(stored['token']).strip()
        exp = int(stored['exp'])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise BootstrapError('admin_jwt_payload_invalid_local') from exc
    if not token or exp <= int(time.time()) + 120:
        raise BootstrapError('admin_jwt_expired_or_too_close_to_expiry')
    return token


def mint_service_token(api_base: str, admin_jwt: str, *, expires_in_days: int = 90) -> str:
    status, payload = request_json('POST', runtime_api_url(api_base, '/v1/admin/service-tokens'), headers={'Authorization': f'Bearer {admin_jwt}', 'X-Correlation-Id': 'pc24x7-token-bootstrap-mint'}, body={'label': LABEL, 'scopes': [SCOPE], 'expires_in_days': expires_in_days})
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


def bootstrap(*, api_base: str, cofre_base: str, vault_token: str, vault_name: str, secret_name: str, allow_provision: bool = True, admin_jwt: str = '', local_cofre_container: str = '') -> BootstrapResult:
    client = keyvault_client(vault_name)
    existing = None
    try:
        existing = client.get_secret(secret_name).value
    except Exception as exc:
        if exc.__class__.__name__ not in {'ResourceNotFoundError', 'SecretNotFound'}:
            raise BootstrapError(f'keyvault_read_failed:{exc.__class__.__name__}') from None

    if existing:
        readiness = validate_service_token(api_base, str(existing))
        if readiness == 200:
            return BootstrapResult(status='ready', environment='dev', secret_name=secret_name, scope=SCOPE, token_created=False, existing_token_reused=True, readiness_http_status=200)
        if not allow_provision:
            raise BootstrapError(f'existing_service_token_readiness_failed:http_{readiness}')
    elif not allow_provision:
        raise BootstrapError('service_token_missing_provisioning_disabled')

    effective_admin_jwt = admin_jwt.strip()
    if not effective_admin_jwt and local_cofre_container:
        effective_admin_jwt = read_admin_jwt_from_local_runtime(local_cofre_container, environment='dev')
    if not effective_admin_jwt:
        effective_admin_jwt = read_admin_jwt(cofre_base, vault_token, environment='dev')
    new_token = mint_service_token(api_base, effective_admin_jwt)
    client.set_secret(secret_name, new_token, tags={'environment': 'dev', 'consumer': LABEL, 'scope': SCOPE, 'source': 'reqsys-service-token'})
    readiness = validate_service_token(api_base, new_token)
    if readiness != 200:
        raise BootstrapError(f'new_service_token_readiness_failed:http_{readiness}')
    return BootstrapResult(status='ready', environment='dev', secret_name=secret_name, scope=SCOPE, token_created=True, existing_token_reused=False, readiness_http_status=readiness)


def main() -> int:
    api_base = os.getenv('REQSYS_API_BASE_URL', DEFAULT_API).strip() or DEFAULT_API
    if not api_base:
        print(json.dumps({'status': 'blocked', 'reason': 'REQSYS_API_BASE_URL_missing', 'secret_value_exposed': False}))
        return 4
    cofre_base = os.getenv('COFRE_API_URL', api_base).strip() or api_base
    vault_token = os.getenv('VAULT_API_TOKEN', '').strip()
    admin_jwt = os.getenv('COFRE_ADMIN_JWT', '').strip()
    local_cofre_container = os.getenv('PC24X7_LOCAL_COFRE_CONTAINER', '').strip()
    vault_name = os.getenv('REQSYS_KEY_VAULT_NAME', '').strip()
    secret_name = os.getenv('PC24X7_TEAMS_SERVICE_TOKEN_SECRET', DEFAULT_SECRET_NAME).strip() or DEFAULT_SECRET_NAME
    allow_provision = os.getenv('PC24X7_TEAMS_ALLOW_PROVISION', 'true').strip().lower() in {'1', 'true', 'yes', 'on'}
    if allow_provision and not admin_jwt and not vault_token and not local_cofre_container:
        print(json.dumps({'status': 'blocked', 'reason': 'ADMIN_CREDENTIAL_missing', 'secret_value_exposed': False}))
        return 4
    if not vault_name:
        print(json.dumps({'status': 'blocked', 'reason': 'REQSYS_KEY_VAULT_NAME_missing', 'secret_value_exposed': False}))
        return 4
    try:
        result = bootstrap(api_base=api_base, cofre_base=cofre_base, vault_token=vault_token, vault_name=vault_name, secret_name=secret_name, allow_provision=allow_provision, admin_jwt=admin_jwt, local_cofre_container=local_cofre_container)
    except BootstrapError as exc:
        print(json.dumps({'status': 'blocked', 'reason': str(exc), 'secret_value_exposed': False}))
        return 4
    print(json.dumps(asdict(result), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
