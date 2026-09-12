import importlib.util
import json
import sys
import time
from pathlib import Path

SCRIPT = Path('scripts/bootstrap_pc24x7_teams_service_token.py')
spec = importlib.util.spec_from_file_location('bootstrap_pc24x7_teams_service_token', SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class FakeSecret:
    def __init__(self, value):
        self.value = value


class FakeClient:
    def __init__(self, existing=None):
        self.existing = existing
        self.set_calls = []

    def get_secret(self, name):
        if self.existing is None:
            class ResourceNotFoundError(Exception):
                pass
            raise ResourceNotFoundError('missing')
        return FakeSecret(self.existing)

    def set_secret(self, name, value, tags=None):
        self.set_calls.append((name, value, tags or {}))
        self.existing = value


def test_reuses_existing_valid_token_without_admin_jwt(monkeypatch):
    client = FakeClient('existing-token')
    monkeypatch.setattr(module, 'keyvault_client', lambda _: client)
    monkeypatch.setattr(module, 'validate_service_token', lambda *_: 200)
    monkeypatch.setattr(module, 'read_admin_jwt', lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError('must not read admin jwt')))
    result = module.bootstrap(
        api_base='https://dev.invalid', cofre_base='https://dev.invalid', vault_token='vault',
        vault_name='kv', secret_name='pc24x7-token',
    )
    assert result.status == 'ready'
    assert result.existing_token_reused is True
    assert result.token_created is False
    assert client.set_calls == []


def test_mints_and_stores_when_secret_missing(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(module, 'keyvault_client', lambda _: client)
    monkeypatch.setattr(module, 'read_admin_jwt', lambda *_args, **_kwargs: 'admin-jwt')
    monkeypatch.setattr(module, 'mint_service_token', lambda *_args, **_kwargs: 'new-service-token')
    monkeypatch.setattr(module, 'validate_service_token', lambda *_: 200)
    result = module.bootstrap(
        api_base='https://dev.invalid', cofre_base='https://dev.invalid', vault_token='vault',
        vault_name='kv', secret_name='pc24x7-token',
    )
    assert result.token_created is True
    assert result.existing_token_reused is False
    assert len(client.set_calls) == 1
    name, value, tags = client.set_calls[0]
    assert name == 'pc24x7-token'
    assert value == 'new-service-token'
    assert tags['scope'] == module.SCOPE


def test_read_admin_jwt_blocks_expired_payload(monkeypatch):
    payload = {'data': {'value': json.dumps({'token': 'jwt', 'exp': int(time.time()) - 1})}}
    monkeypatch.setattr(module, 'request_json', lambda *args, **kwargs: (200, payload))
    try:
        module.read_admin_jwt('https://dev.invalid', 'vault')
        assert False, 'expected BootstrapError'
    except module.BootstrapError as exc:
        assert 'expired_or_too_close' in str(exc)


def test_http_200_without_readiness_does_not_finish(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(module, 'keyvault_client', lambda _: client)
    monkeypatch.setattr(module, 'read_admin_jwt', lambda *_args, **_kwargs: 'admin-jwt')
    monkeypatch.setattr(module, 'mint_service_token', lambda *_args, **_kwargs: 'new-service-token')
    monkeypatch.setattr(module, 'validate_service_token', lambda *_: 503)
    try:
        module.bootstrap(
            api_base='https://dev.invalid', cofre_base='https://dev.invalid', vault_token='vault',
            vault_name='kv', secret_name='pc24x7-token',
        )
        assert False, 'expected BootstrapError'
    except module.BootstrapError as exc:
        assert 'readiness_failed' in str(exc)
