from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api import lifecycle as api
from app.core.service_tokens import ServiceAuthContext
from app.models.requisito import Requisito
from app.services.redmine_lifecycle_batch import RedmineLifecycleBatchError


def _requisito(db_session, codigo: str = 'REQ-168620100') -> Requisito:
    requisito = Requisito(
        codigo=codigo,
        titulo='API lote sync Redmine',
        descricao='Critério de aceite: expor lote governado e liberação de quarentena.',
        urgencia='alta',
        area='Engenharia',
        sistema='ReqSys',
        solicitante='teste@reqsys.local',
        status='em_execucao',
        impacto_regulatorio=False,
    )
    db_session.add(requisito)
    db_session.commit()
    db_session.refresh(requisito)
    return requisito


def _auth() -> ServiceAuthContext:
    return ServiceAuthContext(ator='service-token:redmine-sync', via_token=True)


def test_api_lote_encaminha_politica_de_lock_backoff_e_quarentena(db_session, monkeypatch):
    captured = {}

    def fake_lote(db, **kwargs):
        captured.update(kwargs)
        return {'dry_run': kwargs['dry_run'], 'avaliados': 0, 'contagens': {}, 'itens': []}

    monkeypatch.setattr(api, 'reconciliar_lote', fake_lote)

    response = api.sincronizar_redmine_lote(
        payload=api.LifecycleRedmineBatchIn(dry_run=True, lote_max=3, incluir_quarentena=True),
        db=db_session,
        auth=_auth(),
        x_correlation_id='corr-api-lote',
    )

    assert response['success'] is True
    assert response['meta']['correlation_id'] == 'corr-api-lote'
    assert response['data']['dry_run'] is True
    assert captured['lote_max'] == 3
    assert captured['incluir_quarentena'] is True
    assert captured['actor'] == 'service-token:redmine-sync'
    assert captured['correlation_id'] == 'corr-api-lote'
    # A política de reserva/backoff vem da configuração, não do corpo da requisição.
    assert captured['lock_timeout_minutos'] > 0
    assert captured['max_tentativas'] > 0
    assert captured['backoff_base_minutos'] > 0
    assert captured['backoff_max_minutos'] >= captured['backoff_base_minutos']


def test_api_lote_usa_lote_max_da_configuracao_quando_omitido(db_session, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        api,
        'reconciliar_lote',
        lambda db, **kwargs: captured.update(kwargs) or {'avaliados': 0, 'itens': []},
    )
    monkeypatch.setattr(api.settings, 'redmine_lifecycle_sync_lote_max', 7)

    api.sincronizar_redmine_lote(
        payload=None,
        db=db_session,
        auth=_auth(),
        x_correlation_id=None,
    )

    assert captured['lote_max'] == 7
    assert captured['dry_run'] is False
    assert captured['correlation_id'].startswith('lifecycle-')


def test_api_liberar_quarentena_encaminha_e_converte_bloqueio_em_409(db_session, monkeypatch):
    requisito = _requisito(db_session)
    captured = {}

    monkeypatch.setattr(
        api,
        'liberar_quarentena',
        lambda db, **kwargs: captured.update(kwargs) or {'released': True},
    )
    response = api.liberar_quarentena_redmine(
        requisito.id,
        db=db_session,
        auth=_auth(),
        x_correlation_id='corr-api-liberacao',
    )
    assert response['data']['released'] is True
    assert captured['requisito'].id == requisito.id
    assert captured['actor'] == 'service-token:redmine-sync'

    def fail(*_args, **_kwargs):
        raise RedmineLifecycleBatchError('vínculo Redmine ausente')

    monkeypatch.setattr(api, 'liberar_quarentena', fail)
    with pytest.raises(HTTPException) as exc:
        api.liberar_quarentena_redmine(
            requisito.id,
            db=db_session,
            auth=_auth(),
            x_correlation_id='corr-api-liberacao-erro',
        )
    assert exc.value.status_code == 409
    assert 'vínculo Redmine ausente' in exc.value.detail


def test_api_liberar_quarentena_requisito_inexistente_404(db_session):
    with pytest.raises(HTTPException) as exc:
        api.liberar_quarentena_redmine(
            999999,
            db=db_session,
            auth=_auth(),
            x_correlation_id='corr-api-liberacao-404',
        )
    assert exc.value.status_code == 404
