import importlib.util
import json
from pathlib import Path


SCRIPT = Path('scripts/pc24x7_teams_queue.py')
spec = importlib.util.spec_from_file_location('pc24x7_teams_queue', SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def test_enqueue_is_idempotent_and_contains_no_secret(tmp_path):
    job = module.build_job(provider='gemini', model='gemini-2.5-flash', mensagem='teste', titulo='t')
    first = module.enqueue(tmp_path, job)
    second = module.enqueue(tmp_path, module.build_job(provider='gemini', model='gemini-2.5-flash', mensagem='teste', titulo='t'))
    assert first == second
    payload = first.read_text(encoding='utf-8')
    assert 'token' not in payload.lower()
    assert job['payload_sha256'] in first.name
    assert job['payload']['data_classification'] == 'internal'


def test_build_job_accepts_explicit_public_classification_without_changing_default():
    job = module.build_job(
        provider='gemini',
        model='gemini-2.5-flash',
        mensagem='teste sintético',
        titulo='e2e',
        data_classification='public',
    )
    assert job['payload']['data_classification'] == 'public'


def test_process_success_moves_to_done_and_writes_sanitized_evidence(tmp_path, monkeypatch):
    token_file = tmp_path / 'token.txt'
    token_file.write_text('segredo-nao-vazar', encoding='utf-8')
    job = module.build_job(provider='gemini', model='gemini-2.5-flash', mensagem='teste', titulo='t')
    module.enqueue(tmp_path, job)
    monkeypatch.setattr(module, 'call_reqsys', lambda *args, **kwargs: {
        'data': {
            'duplicate': False,
            'conversation': {'id': 'conv-1'},
            'teams': {'entrega': {'entregue': True, 'canal_usado': 'bot'}},
        }
    })
    result = module.process_one(tmp_path, 'https://dev.invalid', token_file)
    assert result['status'] == 'done'
    assert result['conversation_id'] == 'conv-1'
    assert result['teams_delivered'] is True
    assert result['teams_channel'] == 'bot'
    assert list((tmp_path / 'done').glob('*.json'))
    evidence = json.loads(next((tmp_path / 'evidence').glob('*.json')).read_text(encoding='utf-8'))
    assert evidence['secret_value_exposed'] is False
    assert 'segredo-nao-vazar' not in json.dumps(evidence)


def test_http_200_without_direct_bot_delivery_retries(tmp_path, monkeypatch):
    token_file = tmp_path / 'token.txt'
    token_file.write_text('x', encoding='utf-8')
    job = module.build_job(provider='gemini', model='gemini-2.5-flash', mensagem='teste-sem-entrega', titulo='t')
    module.enqueue(tmp_path, job)
    monkeypatch.setattr(module.time, 'time', lambda: 1000)
    monkeypatch.setattr(module, 'call_reqsys', lambda *args, **kwargs: {
        'data': {
            'duplicate': False,
            'conversation': {'id': 'conv-2'},
            'teams': {'modo': 'fila_gateway', 'entrega': None},
        }
    })
    result = module.process_one(tmp_path, 'https://dev.invalid', token_file)
    assert result['status'] == 'retry'
    assert result['conversation_id'] == 'conv-2'
    assert result['teams_delivered'] is False
    assert result['error'] == 'DeliveryNotConfirmed'
    assert not list((tmp_path / 'done').glob('*.json'))
    assert list((tmp_path / 'pending').glob('*.json'))


def test_http_200_without_conversation_id_retries(tmp_path, monkeypatch):
    token_file = tmp_path / 'token.txt'
    token_file.write_text('x', encoding='utf-8')
    job = module.build_job(provider='gemini', model='gemini-2.5-flash', mensagem='teste-sem-conversa', titulo='t')
    module.enqueue(tmp_path, job)
    monkeypatch.setattr(module.time, 'time', lambda: 1000)
    monkeypatch.setattr(module, 'call_reqsys', lambda *args, **kwargs: {
        'data': {'teams': {'entrega': {'entregue': True, 'canal_usado': 'bot'}}}
    })
    result = module.process_one(tmp_path, 'https://dev.invalid', token_file)
    assert result['status'] == 'retry'
    assert result['conversation_id'] is None
    assert result['error'] == 'DeliveryNotConfirmed'
    assert not list((tmp_path / 'done').glob('*.json'))


def test_reqsys_http_status_is_preserved_without_response_body(tmp_path, monkeypatch):
    token_file = tmp_path / 'token.txt'
    token_file.write_text('x', encoding='utf-8')
    job = module.build_job(provider='gemini', model='gemini-2.5-flash', mensagem='teste-http', titulo='t')
    module.enqueue(tmp_path, job)
    monkeypatch.setattr(module.time, 'time', lambda: 1000)
    monkeypatch.setattr(
        module,
        'call_reqsys',
        lambda *args, **kwargs: (_ for _ in ()).throw(module.ReqSysHTTPError(503)),
    )
    result = module.process_one(tmp_path, 'https://dev.invalid', token_file)
    assert result['status'] == 'retry'
    assert result['error'] == 'http_503'
    serialized = json.dumps(result)
    assert 'response' not in serialized.lower()
    assert result['secret_value_exposed'] is False


def test_failure_retries_then_quarantines(tmp_path, monkeypatch):
    token_file = tmp_path / 'token.txt'
    token_file.write_text('x', encoding='utf-8')
    job = module.build_job(provider='gemini', model='gemini-2.5-flash', mensagem='teste', titulo='t')
    module.enqueue(tmp_path, job)
    monkeypatch.setattr(module, 'MAX_ATTEMPTS', 2)
    monkeypatch.setattr(module, 'call_reqsys', lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('falha')))
    monkeypatch.setattr(module.time, 'time', lambda: 1000)
    first = module.process_one(tmp_path, 'https://dev.invalid', token_file)
    assert first['status'] == 'retry'
    pending = next((tmp_path / 'pending').glob('*.json'))
    data = json.loads(pending.read_text(encoding='utf-8'))
    data['not_before'] = 0
    pending.write_text(json.dumps(data), encoding='utf-8')
    second = module.process_one(tmp_path, 'https://dev.invalid', token_file)
    assert second['status'] == 'quarantined'
    assert list((tmp_path / 'quarantine').glob('*.json'))
