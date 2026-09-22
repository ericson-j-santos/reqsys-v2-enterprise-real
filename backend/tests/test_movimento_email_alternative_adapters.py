import json
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
import requests

from app.services.movimento_email.repository import ExtracaoError
from app.services.movimento_email.snapshot_source import ApiSnapshotRepository, FileSnapshotRepository

REFERENCE = date(2026, 9, 7)


def snapshot():
    return dict(schema_version=1, source_id='reqsys-ci', data_referencia=REFERENCE.isoformat(),
                generated_at=datetime.now(timezone.utc).isoformat(),
                fechamento=[dict(indicador='Total', valor='10')], pendencias_cadastro=[],
                pendencias_historicas=[], pendencias_observacao=[])


def repository(tmp_path, payload):
    (tmp_path / '2026-09-07.json').write_text(json.dumps(payload), encoding='utf-8')
    return FileSnapshotRepository(directory=str(tmp_path), source_id='reqsys-ci', correlation_id='corr-test')


def test_snapshot_consistente_e_rastreavel(tmp_path):
    repo = repository(tmp_path, snapshot())
    assert repo.get_fechamento(REFERENCE)[0].valor == '10'
    (tmp_path / '2026-09-07.json').write_text('invalido', encoding='utf-8')
    assert repo.get_pendencias_cadastro(REFERENCE) == []
    assert len(repo.evidence['sha256']) == 64
    assert repo.evidence['correlation_id'] == 'corr-test'
    with pytest.raises(ExtracaoError):
        repo.get_fechamento(date(2026, 9, 8))


@pytest.mark.parametrize('change', [
    {'schema_version': 2}, {'source_id': 'outra'}, {'data_referencia': '2026-09-06'},
    {'generated_at': '2026-01-01T00:00:00'},
    {'generated_at': (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()},
    {'generated_at': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()},
    {'fechamento': [{'indicador': 'Total'}]}, {'pendencias_cadastro': None},
    {'fechamento': [{'indicador': 'Total', 'valor': 10}]}, {'extra': 'proibido'},
])
def test_snapshot_invalido_falha_fechado(tmp_path, change):
    with pytest.raises(ExtracaoError):
        repository(tmp_path, snapshot() | change).get_fechamento(REFERENCE)


def test_arquivo_ausente(tmp_path):
    repo = FileSnapshotRepository(directory=str(tmp_path), source_id='reqsys-ci', correlation_id='corr-test')
    with pytest.raises(ExtracaoError):
        repo.get_fechamento(REFERENCE)


def test_api_propaga_correlacao_e_nao_segue_redirect(monkeypatch):
    response = MagicMock(status_code=200)
    response.__enter__.return_value = response
    response.iter_content.return_value = [json.dumps(snapshot()).encode()]
    get = MagicMock(return_value=response)
    monkeypatch.setattr(requests, 'get', get)
    repo = ApiSnapshotRepository(url='https://example.com/snapshot', token='placeholder',
                                 source_id='reqsys-ci', correlation_id='corr-test')
    assert repo.get_fechamento(REFERENCE)[0].valor == '10'
    assert get.call_args.kwargs['allow_redirects'] is False
    assert get.call_args.kwargs['headers']['X-Correlation-ID'] == 'corr-test'
    response.status_code = 302
    other = ApiSnapshotRepository(url='https://example.com/snapshot', token='placeholder',
                                  source_id='reqsys-ci', correlation_id='corr-test')
    with pytest.raises(ExtracaoError):
        other.get_fechamento(REFERENCE)


@pytest.mark.parametrize('url', ['http://example.com', 'https://user:pass@example.com', 'https://example.com?token=x'])
def test_api_rejeita_url_insegura(url):
    with pytest.raises(ExtracaoError):
        ApiSnapshotRepository(url=url, token='placeholder', source_id='reqsys-ci', correlation_id='corr-test')


def test_job_snapshot_persiste_evidencia_sem_dados(tmp_path, db_session):
    from app.models.auditoria import AuditoriaEvento
    from app.services.movimento_email.jobs import executar_job_diario
    repo = repository(tmp_path, snapshot())
    result = executar_job_diario(db_session, repo, data_referencia=REFERENCE,
                                correlation_id='corr-test', destinatarios=['recipient@example.com'])
    assert result['status'] == 'PENDING'
    event = db_session.query(AuditoriaEvento).filter_by(acao='MOVIMENTO_EMAIL_FONTE_VALIDADA').one()
    assert json.loads(event.payload_minimo) == repo.evidence
    assert 'fechamento' not in event.payload_minimo


def test_job_snapshot_rejeitado_nao_enfileira(tmp_path, db_session):
    from app.models.movimento_email_dispatch import MovimentoEmailDispatch
    from app.services.movimento_email.jobs import executar_job_diario
    repo = repository(tmp_path, snapshot() | {'schema_version': 99})
    with pytest.raises(ExtracaoError):
        executar_job_diario(db_session, repo, data_referencia=REFERENCE,
                           correlation_id='corr-test', destinatarios=['recipient@example.com'])
    assert db_session.query(MovimentoEmailDispatch).count() == 0


def test_arquivo_grande_rejeitado(tmp_path):
    from app.services.movimento_email.snapshot_source import MAX_BYTES
    repo = repository(tmp_path, snapshot())
    (tmp_path / '2026-09-07.json').write_bytes(b' ' * (MAX_BYTES + 1))
    with pytest.raises(ExtracaoError):
        repo.get_fechamento(REFERENCE)


def test_api_erro_nao_expoe_token(monkeypatch):
    monkeypatch.setattr(requests, 'get', MagicMock(side_effect=requests.Timeout('secret-value')))
    repo = ApiSnapshotRepository(url='https://example.com/snapshot', token='placeholder',
                                 source_id='reqsys-ci', correlation_id='corr-test')
    with pytest.raises(ExtracaoError) as exc:
        repo.get_fechamento(REFERENCE)
    assert 'secret-value' not in str(exc.value)


@pytest.mark.parametrize('timeout', [0, -1, float('nan'), float('inf')])
def test_api_rejeita_timeout_invalido(timeout):
    with pytest.raises(ExtracaoError):
        ApiSnapshotRepository(url='https://example.com/snapshot', token='placeholder',
                              source_id='reqsys-ci', correlation_id='corr-test', timeout_seconds=timeout)
