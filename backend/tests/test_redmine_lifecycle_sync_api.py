from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api import lifecycle as api
from app.core.service_tokens import ServiceAuthContext
from app.models.requisito import Requisito
from app.services.redmine_lifecycle_sync import RedmineLifecycleSyncError


def _requisito(db_session) -> Requisito:
    requisito = Requisito(
        codigo='REQ-168600006',
        titulo='API sync Redmine',
        descricao='Critério de aceite: expor reconciliação governada com dry-run.',
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


def test_api_sync_redmine_encaminha_dry_run_e_correlation(db_session, monkeypatch):
    requisito = _requisito(db_session)
    captured = {}

    def fake_sync(db, **kwargs):
        captured.update(kwargs)
        return {
            'codigo': kwargs['requisito'].codigo,
            'dry_run': kwargs['dry_run'],
            'mutation_count': 0,
        }

    monkeypatch.setattr(api, 'sincronizar_requisito_redmine', fake_sync)

    response = api.sincronizar_redmine_lifecycle(
        requisito.id,
        payload=api.LifecycleRedmineSyncIn(dry_run=True),
        db=db_session,
        auth=_auth(),
        x_correlation_id='corr-api-redmine-sync',
    )

    assert response['success'] is True
    assert response['meta']['correlation_id'] == 'corr-api-redmine-sync'
    assert response['data']['dry_run'] is True
    assert captured['actor'] == 'service-token:redmine-sync'
    assert captured['correlation_id'] == 'corr-api-redmine-sync'


def test_api_sync_redmine_converte_bloqueio_em_409(db_session, monkeypatch):
    requisito = _requisito(db_session)

    def fail_sync(*_args, **_kwargs):
        raise RedmineLifecycleSyncError('vínculo ausente')

    monkeypatch.setattr(api, 'sincronizar_requisito_redmine', fail_sync)

    with pytest.raises(HTTPException) as exc:
        api.sincronizar_redmine_lifecycle(
            requisito.id,
            payload=None,
            db=db_session,
            auth=_auth(),
            x_correlation_id='corr-api-redmine-fail',
        )

    assert exc.value.status_code == 409
    assert 'vínculo ausente' in exc.value.detail
