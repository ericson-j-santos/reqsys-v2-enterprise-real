import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path('scripts').resolve()
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
SCRIPT = SCRIPTS / 'pc24x7_teams_ephemeral_e2e.py'
spec = importlib.util.spec_from_file_location('pc24x7_teams_ephemeral_e2e', SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def ready_payload():
    return {
        'data': {
            'schema_version': '1.0.0',
            'status': 'ready',
            'ready': True,
            'bloqueios': [],
            'conversation_references': 1,
        }
    }


def delivered_payload():
    return {
        'data': {
            'conversation': {'id': 'conv-dev-1'},
            'duplicate': False,
            'teams': {'entrega': {'entregue': True, 'canal_usado': 'bot'}},
        }
    }


def patch_valid_admin(monkeypatch):
    monkeypatch.setattr(
        module,
        'resolve_admin_jwt',
        lambda *_args, **_kwargs: ('admin-jwt', 'environment_secret_valid', False),
    )


def test_resolve_admin_jwt_reuses_valid_environment_secret(monkeypatch):
    calls = []

    def fake_request(method, url, *, headers, body=None):
        calls.append((method, url))
        assert method == 'GET'
        assert url.endswith('/v1/auth/session')
        return 200, {'data': {'papel': 'admin'}}

    monkeypatch.setattr(module, 'request_json', fake_request)
    token, source, recovered = module.resolve_admin_jwt(
        'https://reqsys-api-dev.invalid', 'existing-jwt', 'corr-auth-valid', module.ADMIN_EMAIL_DEFAULT
    )
    assert token == 'existing-jwt'
    assert source == 'environment_secret_valid'
    assert recovered is False
    assert calls == [('GET', 'https://reqsys-api-dev.invalid/v1/auth/session')]


def test_resolve_admin_jwt_recovers_expired_secret_with_dev_demo_login(monkeypatch):
    issued = 'fresh-admin-jwt-never-log'
    calls = []

    def fake_request(method, url, *, headers, body=None):
        calls.append((method, url, body))
        if url.endswith('/v1/auth/session'):
            return 401, {}
        if url.endswith('/v1/auth/config'):
            return 200, {'data': {'environment': 'desenvolvimento', 'demo_login_enabled': True}}
        if url.endswith('/v1/auth/login'):
            assert body == {'email': module.ADMIN_EMAIL_DEFAULT}
            return 200, {'data': {'access_token': issued, 'usuario': {'papel': 'admin'}}}
        raise AssertionError(url)

    monkeypatch.setattr(module, 'request_json', fake_request)
    token, source, recovered = module.resolve_admin_jwt(
        'https://reqsys-api-dev.invalid', 'expired-jwt', 'corr-auth-recover', module.ADMIN_EMAIL_DEFAULT
    )
    assert token == issued
    assert source == 'dev_demo_ephemeral'
    assert recovered is True
    assert [call[1].rsplit('/', 1)[-1] for call in calls] == ['session', 'config', 'login']


def test_dev_demo_login_disabled_fails_closed(monkeypatch):
    def fake_request(method, url, *, headers, body=None):
        if url.endswith('/v1/auth/session'):
            return 401, {}
        if url.endswith('/v1/auth/config'):
            return 200, {'data': {'environment': 'desenvolvimento', 'demo_login_enabled': False}}
        raise AssertionError(url)

    monkeypatch.setattr(module, 'request_json', fake_request)
    with pytest.raises(module.EphemeralE2EError, match='admin_auth_unavailable:demo_login_disabled'):
        module.resolve_admin_jwt(
            'https://reqsys-api-dev.invalid', 'expired-jwt', 'corr-auth-disabled', module.ADMIN_EMAIL_DEFAULT
        )


def test_production_auth_is_refused_before_login(monkeypatch):
    def fake_request(method, url, *, headers, body=None):
        if url.endswith('/v1/auth/config'):
            return 200, {'data': {'environment': 'producao', 'demo_login_enabled': True}}
        raise AssertionError('production login must not be called')

    monkeypatch.setattr(module, 'request_json', fake_request)
    with pytest.raises(module.EphemeralE2EError, match='admin_auth_refused:production'):
        module.mint_dev_admin_jwt(
            'https://reqsys-api-dev.invalid', 'corr-prod-refused', module.ADMIN_EMAIL_DEFAULT
        )


def test_success_uses_minimum_scope_proves_delivery_idempotency_and_revokes(monkeypatch):
    secret = 'service-token-must-never-appear'
    calls = []
    patch_valid_admin(monkeypatch)

    def fake_request(method, url, *, headers, body=None):
        calls.append((method, url, body))
        if method == 'POST':
            return 201, {'data': {'id': 77, 'token': secret}}
        if method == 'GET':
            return 200, ready_payload()
        if method == 'DELETE':
            return 200, {'data': {'id': 77, 'revogado': True}}
        raise AssertionError(method)

    def fake_call_reqsys(_base_url, token, _job):
        assert token == secret
        return delivered_payload()

    monkeypatch.setattr(module, 'request_json', fake_request)
    monkeypatch.setattr(module.queue, 'call_reqsys', fake_call_reqsys)

    evidence = module.execute_e2e(
        api_base='https://reqsys-api-dev.invalid',
        admin_jwt='admin-jwt',
        correlation_id='corr-success-001',
        provider='gemini',
        model='gemini-2.5-flash',
    )

    assert evidence['status'] == 'done'
    assert evidence['admin_auth_source'] == 'environment_secret_valid'
    assert evidence['admin_auth_recovered'] is False
    assert evidence['token_created'] is True
    assert evidence['token_revoked'] is True
    assert evidence['readiness']['http_status'] == 200
    assert evidence['readiness']['ready'] is True
    assert evidence['delivery']['conversation_id'] == 'conv-dev-1'
    assert evidence['delivery']['teams_delivered'] is True
    assert evidence['delivery']['teams_channel'] == 'bot'
    assert evidence['queue_idempotency_proven'] is True
    assert evidence['secret_value_exposed'] is False
    assert evidence['production_touched'] is False
    assert evidence['test_touched'] is False
    assert secret not in json.dumps(evidence)

    create = next(call for call in calls if call[0] == 'POST')
    assert create[2]['scopes'] == [module.SCOPE]
    assert create[2]['expires_in_days'] == 1
    assert any(call[0] == 'DELETE' and call[1].endswith('/77') for call in calls)


def test_readiness_blocked_still_revokes_and_never_calls_delivery(monkeypatch):
    delivery_called = False
    patch_valid_admin(monkeypatch)

    def fake_request(method, url, *, headers, body=None):
        if method == 'POST':
            return 201, {'data': {'id': 88, 'token': 'ephemeral-secret'}}
        if method == 'GET':
            return 200, {
                'data': {
                    'schema_version': '1.0.0',
                    'status': 'blocked',
                    'ready': False,
                    'conversation_references': 0,
                    'bloqueios': [{'codigo': 'CONVERSATION_REFERENCE_AUSENTE'}],
                }
            }
        if method == 'DELETE':
            return 200, {'data': {'id': 88, 'revogado': True}}
        raise AssertionError(method)

    def fake_delivery(*_args, **_kwargs):
        nonlocal delivery_called
        delivery_called = True
        raise AssertionError('delivery must not run when readiness is blocked')

    monkeypatch.setattr(module, 'request_json', fake_request)
    monkeypatch.setattr(module.queue, 'call_reqsys', fake_delivery)

    evidence = module.execute_e2e(
        api_base='https://reqsys-api-dev.invalid',
        admin_jwt='admin-jwt',
        correlation_id='corr-readiness-blocked',
        provider='gemini',
        model='gemini-2.5-flash',
    )

    assert evidence['status'] == 'blocked'
    assert evidence['error'] == 'readiness_not_ready'
    assert evidence['readiness']['blocker_codes'] == ['CONVERSATION_REFERENCE_AUSENTE']
    assert evidence['token_revoked'] is True
    assert delivery_called is False


def test_delivery_failure_still_revokes(monkeypatch):
    deleted = False
    patch_valid_admin(monkeypatch)

    def fake_request(method, url, *, headers, body=None):
        nonlocal deleted
        if method == 'POST':
            return 201, {'data': {'id': 99, 'token': 'ephemeral-secret'}}
        if method == 'GET':
            return 200, ready_payload()
        if method == 'DELETE':
            deleted = True
            return 200, {'data': {'id': 99, 'revogado': True}}
        raise AssertionError(method)

    monkeypatch.setattr(module, 'request_json', fake_request)
    monkeypatch.setattr(
        module.queue,
        'call_reqsys',
        lambda *_args, **_kwargs: {
            'data': {
                'conversation': {'id': 'conv-dev-2'},
                'teams': {'entrega': {'entregue': False, 'canal_usado': 'bot'}},
            }
        },
    )

    evidence = module.execute_e2e(
        api_base='https://reqsys-api-dev.invalid',
        admin_jwt='admin-jwt',
        correlation_id='corr-delivery-failure',
        provider='gemini',
        model='gemini-2.5-flash',
    )

    assert evidence['status'] == 'blocked'
    assert evidence['error'] == 'teams_delivery_not_done'
    assert evidence['token_revoked'] is True
    assert deleted is True


def test_revoke_failure_fails_closed_even_after_delivery(monkeypatch):
    patch_valid_admin(monkeypatch)

    def fake_request(method, url, *, headers, body=None):
        if method == 'POST':
            return 201, {'data': {'id': 111, 'token': 'ephemeral-secret'}}
        if method == 'GET':
            return 200, ready_payload()
        if method == 'DELETE':
            return 503, {}
        raise AssertionError(method)

    monkeypatch.setattr(module, 'request_json', fake_request)
    monkeypatch.setattr(module.queue, 'call_reqsys', lambda *_args, **_kwargs: delivered_payload())

    evidence = module.execute_e2e(
        api_base='https://reqsys-api-dev.invalid',
        admin_jwt='admin-jwt',
        correlation_id='corr-revoke-failure',
        provider='gemini',
        model='gemini-2.5-flash',
    )

    assert evidence['token_created'] is True
    assert evidence['token_revoked'] is False
    assert evidence['status'] == 'blocked'
    assert evidence['error'] == 'token_revoke_not_confirmed'


def test_auth_recovery_failure_blocks_before_token_creation(monkeypatch):
    monkeypatch.setattr(
        module,
        'resolve_admin_jwt',
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            module.EphemeralE2EError('admin_auth_unavailable:demo_login_disabled')
        ),
    )
    evidence = module.execute_e2e(
        api_base='https://reqsys-api-dev.invalid',
        admin_jwt='',
        correlation_id='corr-no-admin',
        provider='gemini',
        model='gemini-2.5-flash',
    )
    assert evidence['status'] == 'blocked'
    assert evidence['token_created'] is False
    assert evidence['error'] == 'admin_auth_unavailable:demo_login_disabled'
