import importlib.util
import json
import sys
from pathlib import Path

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
            'teams': {
                'entrega': {
                    'entregue': True,
                    'canal_usado': 'bot',
                }
            },
        }
    }


def test_success_uses_minimum_scope_proves_delivery_idempotency_and_revokes(monkeypatch):
    secret = 'service-token-must-never-appear'
    calls = []

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


def test_missing_admin_jwt_blocks_before_token_creation(monkeypatch):
    monkeypatch.setattr(
        module,
        'request_json',
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError('network must not run')),
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
    assert evidence['error'] == 'COFRE_ADMIN_JWT_missing'
