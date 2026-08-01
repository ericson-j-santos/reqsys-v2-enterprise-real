import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / 'scripts' / 'validar_teams_notification_control_center_runtime.py'
spec = importlib.util.spec_from_file_location('teams_smoke', MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def result(status, body=None, error=None):
    return module.HttpResult(status, body, error, 5)


def test_authenticated_smoke_healthy():
    def fake(url, *, method='GET', payload=None, token=None, timeout=25):
        if url.endswith('/health'):
            return result(200, {'status': 'healthy'})
        if url.endswith('/v1/auth/config'):
            return result(200, {'success': True, 'data': {'demo_login_enabled': True}})
        if url.endswith('/v1/auth/login'):
            return result(200, {'success': True, 'data': {'access_token': 'token'}})
        if '/notificacoes/dashboard' in url:
            if token:
                return result(200, {'success': True, 'data': {
                    'schema_version': '1.0.0', 'pendentes': 0, 'processando': 0,
                    'enviados': 1, 'falhas': 0, 'cobertura': {},
                }})
            return result(401, {'detail': 'Token não fornecido'})
        if '/notificacoes/' in url:
            return result(200, {'success': True, 'data': []}) if token else result(401, {})
        raise AssertionError(url)

    payload = module.validate_environment(
        'dev', {'api_url': 'https://example.test'}, timeout=1,
        require_authenticated=True, send_canary=False, request_fn=fake,
    )
    assert payload['ok'] is True
    assert payload['status'] == 'healthy'
    assert payload['auth_source'] == 'demo_login'


def test_smoke_degraded_without_token_is_non_blocking():
    def fake(url, *, method='GET', payload=None, token=None, timeout=25):
        if url.endswith('/health'):
            return result(200, {'status': 'healthy'})
        if url.endswith('/v1/auth/config'):
            return result(200, {'success': True, 'data': {'demo_login_enabled': False}})
        if '/notificacoes/' in url:
            return result(401, {})
        raise AssertionError(url)

    payload = module.validate_environment(
        'prod', {'api_url': 'https://example.test'}, timeout=1,
        require_authenticated=False, send_canary=False, request_fn=fake,
    )
    assert payload['ok'] is True
    assert payload['status'] == 'degraded'
    assert payload['authenticated_checks'] == []


def test_missing_protected_route_fails():
    def fake(url, *, method='GET', payload=None, token=None, timeout=25):
        if url.endswith('/health'):
            return result(200, {'status': 'healthy'})
        if url.endswith('/v1/auth/config'):
            return result(200, {'success': True, 'data': {'demo_login_enabled': False}})
        if '/notificacoes/dashboard' in url:
            return result(404, {})
        if '/notificacoes/' in url:
            return result(401, {})
        raise AssertionError(url)

    payload = module.validate_environment(
        'hml', {'api_url': 'https://example.test'}, timeout=1,
        require_authenticated=False, send_canary=False, request_fn=fake,
    )
    assert payload['ok'] is False
    assert payload['status'] == 'failed'


def test_invalid_governed_token_is_blocking(monkeypatch):
    monkeypatch.setenv('REQSYS_TEAMS_SMOKE_BEARER_TOKEN', 'invalid-token')

    def fake(url, *, method='GET', payload=None, token=None, timeout=25):
        if url.endswith('/health'):
            return result(200, {'status': 'healthy'})
        if url.endswith('/v1/auth/config'):
            return result(200, {'success': True, 'data': {'demo_login_enabled': False}})
        if '/notificacoes/' in url:
            return result(401, {})
        raise AssertionError(url)

    payload = module.validate_environment(
        'prod', {'api_url': 'https://example.test'}, timeout=1,
        require_authenticated=False, send_canary=False, request_fn=fake,
    )
    assert payload['ok'] is False
    assert payload['status'] == 'failed'
