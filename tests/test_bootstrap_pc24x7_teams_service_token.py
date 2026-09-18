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
    result = module.bootstrap(api_base='https://dev.invalid', cofre_base='https://dev.invalid', vault_token='vault', vault_name='kv', secret_name='pc24x7-token')
    assert result.status == 'ready'
    assert result.existing_token_reused is True
    assert result.token_created is False
    assert client.set_calls == []


def test_validation_only_blocks_before_mint_when_existing_token_invalid(monkeypatch):
    client = FakeClient('stale-token')
    monkeypatch.setattr(module, 'keyvault_client', lambda _: client)
    monkeypatch.setattr(module, 'validate_service_token', lambda *_: 401)
    monkeypatch.setattr(module, 'read_admin_jwt', lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError('must not read admin jwt')))
    monkeypatch.setattr(module, 'mint_service_token', lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError('must not mint token')))
    try:
        module.bootstrap(api_base='https://dev.invalid', cofre_base='https://dev.invalid', vault_token='vault', vault_name='kv', secret_name='pc24x7-token', allow_provision=False)
        assert False, 'expected BootstrapError'
    except module.BootstrapError as exc:
        assert str(exc) == 'existing_service_token_readiness_failed:http_401'
    assert client.set_calls == []


def test_validation_only_blocks_when_secret_missing(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(module, 'keyvault_client', lambda _: client)
    monkeypatch.setattr(module, 'read_admin_jwt', lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError('must not read admin jwt')))
    monkeypatch.setattr(module, 'mint_service_token', lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError('must not mint token')))
    try:
        module.bootstrap(api_base='https://dev.invalid', cofre_base='https://dev.invalid', vault_token='vault', vault_name='kv', secret_name='pc24x7-token', allow_provision=False)
        assert False, 'expected BootstrapError'
    except module.BootstrapError as exc:
        assert str(exc) == 'service_token_missing_provisioning_disabled'
    assert client.set_calls == []


def test_validation_only_main_does_not_require_vault_api_token(monkeypatch, capsys):
    monkeypatch.setenv('PC24X7_TEAMS_ALLOW_PROVISION', 'false')
    monkeypatch.setenv('REQSYS_KEY_VAULT_NAME', 'kv')
    monkeypatch.delenv('VAULT_API_TOKEN', raising=False)
    monkeypatch.setattr(module, 'bootstrap', lambda **kwargs: module.BootstrapResult(status='ready', environment='dev', secret_name=kwargs['secret_name'], scope=module.SCOPE, token_created=False, existing_token_reused=True, readiness_http_status=200))
    assert module.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload['status'] == 'ready'
    assert payload['token_created'] is False
    assert payload['existing_token_reused'] is True


def test_mints_and_stores_when_secret_missing(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(module, 'keyvault_client', lambda _: client)
    monkeypatch.setattr(module, 'read_admin_jwt', lambda *_args, **_kwargs: 'admin-jwt')
    monkeypatch.setattr(module, 'mint_service_token', lambda *_args, **_kwargs: 'new-service-token')
    monkeypatch.setattr(module, 'validate_service_token', lambda *_: 200)
    result = module.bootstrap(api_base='https://dev.invalid', cofre_base='https://dev.invalid', vault_token='vault', vault_name='kv', secret_name='pc24x7-token')
    assert result.token_created is True
    assert result.existing_token_reused is False
    assert len(client.set_calls) == 1
    name, value, tags = client.set_calls[0]
    assert name == 'pc24x7-token'
    assert value == 'new-service-token'
    assert tags['scope'] == module.SCOPE


def test_direct_admin_jwt_mints_without_vault_lookup(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(module, 'keyvault_client', lambda _: client)
    monkeypatch.setattr(module, 'read_admin_jwt', lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError('cofre lookup must not run')))
    seen = {}
    def mint(_api, jwt, **_kwargs):
        seen['jwt'] = jwt
        return 'new-service-token'
    monkeypatch.setattr(module, 'mint_service_token', mint)
    monkeypatch.setattr(module, 'validate_service_token', lambda *_: 200)
    result = module.bootstrap(api_base='https://dev.invalid', cofre_base='https://dev.invalid', vault_token='', vault_name='kv', secret_name='pc24x7-token', admin_jwt='admin-from-environment')
    assert seen['jwt'] == 'admin-from-environment'
    assert result.token_created is True
    assert result.readiness_http_status == 200
    assert client.set_calls[0][1] == 'new-service-token'


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
        module.bootstrap(api_base='https://dev.invalid', cofre_base='https://dev.invalid', vault_token='vault', vault_name='kv', secret_name='pc24x7-token')
        assert False, 'expected BootstrapError'
    except module.BootstrapError as exc:
        assert 'readiness_failed' in str(exc)
