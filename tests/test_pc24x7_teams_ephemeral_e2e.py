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
            'providers_configurados': ['gemini', 'groq'],
            'conversation_references': 1,
        }
    }


def creation_payload(conversation_id='conv-dev-1'):
    return {
        'data': {
            'conversation': {'id': conversation_id},
            'duplicate': False,
            'teams': None,
        }
    }


def reply_payload(*, conversation_id='conv-dev-1', duplicate=False, delivered=True, channel='bot'):
    return {
        'data': {
            'conversation_id': conversation_id,
            'duplicate': duplicate,
            'teams': {
                'entrega': {'entregue': delivered, 'canal_usado': channel}
            } if delivered else None,
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


def _success_request_recorder(calls, secret='service-token-must-never-appear'):
    reply_count = {'value': 0}

    def fake_request(method, url, *, headers, body=None):
        calls.append((method, url, body, headers))
        if method == 'POST' and url.endswith('/v1/admin/service-tokens'):
            return 201, {'data': {'id': 77, 'token': secret}}
        if method == 'GET' and url.endswith('/readiness'):
            return 200, ready_payload()
        if method == 'POST' and url.endswith('/ai-conversations'):
            assert body['enviar_teams'] is False
            return 200, creation_payload()
        if method == 'POST' and url.endswith('/conv-dev-1/reply'):
            reply_count['value'] += 1
            if reply_count['value'] == 1:
                assert body['enviar_teams'] is True
                return 200, reply_payload(duplicate=False, delivered=True)
            assert body['enviar_teams'] is False
            return 200, reply_payload(duplicate=True, delivered=False)
        if method == 'DELETE' and url.endswith('/77'):
            return 200, {'data': {'id': 77, 'revogado': True}}
        raise AssertionError((method, url, body))

    return fake_request


def test_success_separates_creation_delivery_proves_idempotency_and_revokes(monkeypatch):
    secret = 'service-token-must-never-appear'
    calls = []
    patch_valid_admin(monkeypatch)
    monkeypatch.setattr(module, 'request_json', _success_request_recorder(calls, secret))

    evidence = module.execute_e2e(
        api_base='https://reqsys-api-dev.invalid',
        admin_jwt='admin-jwt',
        correlation_id='corr-success-001',
        provider='gemini',
        model='gemini-2.5-flash',
    )

    assert evidence['status'] == 'done'
    assert evidence['token_created'] is True
    assert evidence['token_revoked'] is True
    assert evidence['conversation']['conversation_id'] == 'conv-dev-1'
    assert evidence['conversation']['http_status'] == 200
    assert len(evidence['delivery_attempts']) == 1
    assert evidence['delivery_attempts'][0]['teams_delivered'] is True
    assert evidence['turn_idempotency_proven'] is True
    assert evidence['secret_value_exposed'] is False
    assert secret not in json.dumps(evidence)

    creates = [call for call in calls if call[0] == 'POST' and call[1].endswith('/ai-conversations')]
    replies = [call for call in calls if call[0] == 'POST' and '/reply' in call[1]]
    assert len(creates) == 1
    assert len(replies) == 2
    assert replies[0][2]['idempotency_key'] == replies[1][2]['idempotency_key']
    assert replies[0][2]['enviar_teams'] is True
    assert replies[1][2]['enviar_teams'] is False
    assert replies[0][3]['X-Tenant-ID'] == 'reqsys-dev'
    assert replies[0][3]['X-Area-ID'] == 'teams-gateway'


def test_http_500_delivery_retry_reuses_same_conversation_and_turn(monkeypatch):
    calls = []
    patch_valid_admin(monkeypatch)
    reply_count = {'value': 0}

    def fake_request(method, url, *, headers, body=None):
        calls.append((method, url, body))
        if method == 'POST' and url.endswith('/v1/admin/service-tokens'):
            return 201, {'data': {'id': 88, 'token': 'ephemeral-secret'}}
        if method == 'GET' and url.endswith('/readiness'):
            return 200, ready_payload()
        if method == 'POST' and url.endswith('/ai-conversations'):
            return 200, creation_payload()
        if method == 'POST' and url.endswith('/conv-dev-1/reply'):
            reply_count['value'] += 1
            if reply_count['value'] == 1:
                return 500, {}
            if reply_count['value'] == 2:
                return 200, reply_payload(duplicate=True, delivered=True)
            return 200, reply_payload(duplicate=True, delivered=False)
        if method == 'DELETE' and url.endswith('/88'):
            return 200, {'data': {'id': 88, 'revogado': True}}
        raise AssertionError((method, url))

    monkeypatch.setattr(module, 'request_json', fake_request)
    evidence = module.execute_e2e(
        api_base='https://reqsys-api-dev.invalid',
        admin_jwt='admin-jwt',
        correlation_id='corr-retry-same-conv',
        provider='groq',
        model='llama-3.3-70b-versatile',
    )

    assert evidence['status'] == 'done'
    assert evidence['conversation']['conversation_id'] == 'conv-dev-1'
    assert [item['http_status'] for item in evidence['delivery_attempts']] == [500, 200]
    assert evidence['delivery_attempts'][1]['duplicate'] is True
    assert evidence['turn_idempotency_proven'] is True
    creates = [call for call in calls if call[0] == 'POST' and call[1].endswith('/ai-conversations')]
    replies = [call for call in calls if call[0] == 'POST' and '/reply' in call[1]]
    assert len(creates) == 1
    assert len(replies) == 3
    assert len({call[2]['idempotency_key'] for call in replies}) == 1


def test_persistent_delivery_failure_preserves_conversation_id_and_revokes(monkeypatch):
    patch_valid_admin(monkeypatch)
    reply_count = {'value': 0}

    def fake_request(method, url, *, headers, body=None):
        if method == 'POST' and url.endswith('/v1/admin/service-tokens'):
            return 201, {'data': {'id': 99, 'token': 'ephemeral-secret'}}
        if method == 'GET' and url.endswith('/readiness'):
            return 200, ready_payload()
        if method == 'POST' and url.endswith('/ai-conversations'):
            return 200, creation_payload('conv-preserved')
        if method == 'POST' and url.endswith('/conv-preserved/reply'):
            reply_count['value'] += 1
            return (500, {}) if reply_count['value'] == 1 else (409, {})
        if method == 'DELETE' and url.endswith('/99'):
            return 200, {'data': {'id': 99, 'revogado': True}}
        raise AssertionError((method, url))

    monkeypatch.setattr(module, 'request_json', fake_request)
    evidence = module.execute_e2e(
        api_base='https://reqsys-api-dev.invalid',
        admin_jwt='admin-jwt',
        correlation_id='corr-delivery-failure',
        provider='groq',
        model='llama-3.3-70b-versatile',
    )

    assert evidence['status'] == 'blocked'
    assert evidence['conversation']['conversation_id'] == 'conv-preserved'
    assert [item['http_status'] for item in evidence['delivery_attempts']] == [500, 409]
    assert evidence['error'] == 'teams_delivery_not_confirmed:http_409'
    assert evidence['token_revoked'] is True


def test_readiness_blocked_still_revokes_and_never_creates_conversation(monkeypatch):
    patch_valid_admin(monkeypatch)
    created = False

    def fake_request(method, url, *, headers, body=None):
        nonlocal created
        if method == 'POST' and url.endswith('/v1/admin/service-tokens'):
            return 201, {'data': {'id': 100, 'token': 'ephemeral-secret'}}
        if method == 'GET' and url.endswith('/readiness'):
            return 200, {
                'data': {
                    'schema_version': '1.0.0',
                    'status': 'blocked',
                    'ready': False,
                    'conversation_references': 0,
                    'bloqueios': [{'codigo': 'CONVERSATION_REFERENCE_AUSENTE'}],
                }
            }
        if method == 'POST' and url.endswith('/ai-conversations'):
            created = True
            raise AssertionError('conversation must not be created when readiness is blocked')
        if method == 'DELETE' and url.endswith('/100'):
            return 200, {'data': {'id': 100, 'revogado': True}}
        raise AssertionError((method, url))

    monkeypatch.setattr(module, 'request_json', fake_request)
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
    assert created is False


def test_revoke_failure_fails_closed_even_after_delivery(monkeypatch):
    patch_valid_admin(monkeypatch)
    calls = []
    base_fake = _success_request_recorder(calls, 'ephemeral-secret')

    def fake_request(method, url, *, headers, body=None):
        if method == 'DELETE':
            return 503, {}
        return base_fake(method, url, headers=headers, body=body)

    monkeypatch.setattr(module, 'request_json', fake_request)
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
