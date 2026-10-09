import importlib.util
import sys
from pathlib import Path

SCRIPT = Path('scripts/report_builder_email_dev_e2e.py')
spec = importlib.util.spec_from_file_location('report_builder_email_dev_e2e', SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_dry_run_precede_envio_e_nao_inventa_readback(monkeypatch):
    calls = []

    def fake_request(_url, _token, payload):
        calls.append(payload['dry_run'])
        if payload['dry_run']:
            return 200, {'data': {'status': 'planned'}}
        return 200, {'data': {'status': 'accepted_by_provider', 'correlation_id': 'corr-1', 'report': {'definition_sha256': 'a' * 64}, 'delivery': {'provider': 'graph', 'provider_accepted': True, 'recipient_delivery_confirmed': False, 'recipient_delivery_evidence': 'not_observed'}}}

    monkeypatch.setattr(module, 'request_json', fake_request)
    result = module.execute(api_base='https://dev.invalid', token='secret', recipient=module.RECIPIENT, confirm=module.CONFIRM)
    assert calls == [True, False]
    assert result['status'] == 'accepted_pending_recipient_readback'
    assert result['recipient_delivery_confirmed'] is False
    assert result['secret_value_exposed'] is False


def test_bloqueia_destinatario_nao_allowlisted():
    try:
        module.execute(api_base='https://dev.invalid', token='secret', recipient='other@example.com', confirm=module.CONFIRM)
        assert False
    except module.E2EError as exc:
        assert str(exc) == 'recipient_not_allowlisted'


def test_bloqueia_sem_confirmacao_exata():
    try:
        module.execute(api_base='https://dev.invalid', token='secret', recipient=module.RECIPIENT, confirm='SEND')
        assert False
    except module.E2EError as exc:
        assert str(exc) == 'explicit_confirmation_missing'
