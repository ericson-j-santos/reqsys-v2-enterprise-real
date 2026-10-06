import importlib.util
import json
import sys
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
    result = module.bootstrap(api_base='https://dev.invalid', vault_name='kv', secret_name='pc24x7-token')
    assert result.status == 'ready'
    assert result.existing_token_reused is True
    assert result.token_created is False
    assert client.set_calls == []


def test_validation_only_blocks_before_mint_when_existing_token_invalid(monkeypatch):
    client = FakeClient('stale-token')
    monkeypatch.setattr(module, 'keyvault_client', lambda _: client)
    monkeypatch.setattr(module, 'validate_service_token', lambda *_: 401)
    monkeypatch.setattr(module, 'mint_service_token_from_local_runtime', lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError('must not mint token')))
    try:
        module.bootstrap(api_base='https://dev.invalid', vault_name='kv', secret_name='pc24x7-token', allow_provision=False)
        assert False, 'expected BootstrapError'
    except module.BootstrapError as exc:
        assert str(exc) == 'existing_service_token_readiness_failed:http_401'
    assert client.set_calls == []


def test_validation_only_blocks_when_secret_missing(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(module, 'keyvault_client', lambda _: client)
    monkeypatch.setattr(module, 'mint_service_token_from_local_runtime', lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError('must not mint token')))
    try:
        module.bootstrap(api_base='https://dev.invalid', vault_name='kv', secret_name='pc24x7-token', allow_provision=False)
        assert False, 'expected BootstrapError'
    except module.BootstrapError as exc:
        assert str(exc) == 'service_token_missing_provisioning_disabled'
    assert client.set_calls == []


def test_validation_only_main_does_not_require_vault_api_token(monkeypatch, capsys):
    monkeypatch.setenv('REQSYS_API_BASE_URL', 'https://pc24x7-dev.invalid')
    monkeypatch.setenv('PC24X7_TEAMS_ALLOW_PROVISION', 'false')
    monkeypatch.setenv('REQSYS_KEY_VAULT_NAME', 'kv')
    monkeypatch.delenv('VAULT_API_TOKEN', raising=False)
    monkeypatch.setattr(module, 'bootstrap', lambda **kwargs: module.BootstrapResult(status='ready', environment='dev', secret_name=kwargs['secret_name'], scope=module.SCOPE, token_created=False, existing_token_reused=True, readiness_http_status=200))
    assert module.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload['status'] == 'ready'
    assert payload['token_created'] is False
    assert payload['existing_token_reused'] is True


def test_main_falha_fechado_sem_runtime_pc24x7_resolvido(monkeypatch, capsys):
    monkeypatch.delenv('REQSYS_API_BASE_URL', raising=False)
    monkeypatch.setenv('REQSYS_KEY_VAULT_NAME', 'kv')
    assert module.DEFAULT_API == ''
    assert module.main() == 4
    payload = json.loads(capsys.readouterr().out)
    assert payload['status'] == 'blocked'
    assert payload['reason'] == 'REQSYS_API_BASE_URL_missing'
    assert payload['secret_value_exposed'] is False


def test_mints_and_stores_when_secret_missing(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(module, 'keyvault_client', lambda _: client)
    monkeypatch.setattr(module, 'mint_service_token_from_local_runtime', lambda *_args, **_kwargs: 'new-service-token')
    monkeypatch.setattr(module, 'validate_service_token', lambda *_: 200)
    result = module.bootstrap(api_base='https://dev.invalid', vault_name='kv', secret_name='pc24x7-token', local_cofre_container=module.DEFAULT_LOCAL_COFRE_CONTAINER)
    assert result.token_created is True
    assert result.existing_token_reused is False
    assert len(client.set_calls) == 1
    name, value, tags = client.set_calls[0]
    assert name == 'pc24x7-token'
    assert value == 'new-service-token'
    assert tags['scope'] == module.SCOPE


def test_provisioning_requires_local_dev_runtime(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(module, 'keyvault_client', lambda _: client)
    try:
        module.bootstrap(api_base='https://dev.invalid', vault_name='kv', secret_name='pc24x7-token')
        assert False, 'expected BootstrapError'
    except module.BootstrapError as exc:
        assert str(exc) == 'local_dev_runtime_required_for_provisioning'


def test_local_runtime_admin_jwt_precedes_vault_api_lookup(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(module, 'keyvault_client', lambda _: client)
    monkeypatch.setattr(module, 'mint_service_token_from_local_runtime', lambda *_args, **_kwargs: 'new-service-token')
    monkeypatch.setattr(module, 'validate_service_token', lambda *_: 200)
    result = module.bootstrap(
        api_base='https://dev.invalid',
        vault_name='kv',
        secret_name='pc24x7-token',
        local_cofre_container=module.DEFAULT_LOCAL_COFRE_CONTAINER,
    )
    assert result.token_created is True


def test_local_runtime_reader_fails_closed_when_secret_is_absent(monkeypatch):
    class Completed:
        returncode = 0
        stdout = '\n'
        stderr = ''

    monkeypatch.setattr(module.subprocess, 'run', lambda *args, **kwargs: Completed())
    try:
        module.mint_service_token_from_local_runtime(module.DEFAULT_LOCAL_COFRE_CONTAINER, 'https://dev.invalid')
        assert False, 'expected BootstrapError'
    except module.BootstrapError as exc:
        assert str(exc) == 'local_cofre_mint_empty_token'


def test_local_runtime_reader_blocks_non_dev_container():
    try:
        module.mint_service_token_from_local_runtime('reqsys-api-prod', 'https://prod.invalid')
        assert False, 'expected BootstrapError'
    except module.BootstrapError as exc:
        assert str(exc) == 'local_cofre_target_blocked'


def test_local_runtime_mint_uses_dev_only_internal_command(monkeypatch):
    seen = {}

    class Completed:
        returncode = 0
        stdout = 'new-service-token\n'
        stderr = ''

    def fake_run(args, **kwargs):
        seen['args'] = args
        seen['kwargs'] = kwargs
        return Completed()

    monkeypatch.setattr(module.subprocess, 'run', fake_run)
    token = module.mint_service_token_from_local_runtime(
        module.DEFAULT_LOCAL_COFRE_CONTAINER,
        'https://dev.invalid',
    )
    assert token == 'new-service-token'
    assert seen['args'][0:6] == [
        'docker', 'exec', module.DEFAULT_LOCAL_COFRE_CONTAINER, 'python', '-m',
        'app.core.dev_service_token_bootstrap',
    ]
    assert seen['args'][-6:] == ['--label', module.LABEL, '--scope', module.SCOPE, '--expires-in-days', '90']
    assert 'input' not in seen['kwargs']


def test_http_200_without_readiness_does_not_finish(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(module, 'keyvault_client', lambda _: client)
    monkeypatch.setattr(module, 'mint_service_token_from_local_runtime', lambda *_args, **_kwargs: 'new-service-token')
    monkeypatch.setattr(module, 'validate_service_token', lambda *_: 503)
    try:
        module.bootstrap(api_base='https://dev.invalid', vault_name='kv', secret_name='pc24x7-token', local_cofre_container=module.DEFAULT_LOCAL_COFRE_CONTAINER)
        assert False, 'expected BootstrapError'
    except module.BootstrapError as exc:
        assert 'readiness_failed' in str(exc)

def test_runtime_api_url_uses_public_gateway_prefix_exactly_once():
    assert (
        module.runtime_api_url('https://pc24x7-dev.invalid', '/v1/admin/service-tokens')
        == 'https://pc24x7-dev.invalid/api/v1/admin/service-tokens'
    )
    assert (
        module.runtime_api_url('https://pc24x7-dev.invalid/api', '/v1/admin/service-tokens')
        == 'https://pc24x7-dev.invalid/api/v1/admin/service-tokens'
    )

