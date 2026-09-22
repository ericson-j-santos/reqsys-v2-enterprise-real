from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api import lifecycle as api
from app.core.service_tokens import ServiceAuthContext
from app.models.requisito import Requisito


def _requisito(db_session, codigo: str = 'REQ-246813579') -> Requisito:
    requisito = Requisito(
        codigo=codigo,
        titulo='Lifecycle API',
        descricao='Validar contrato HTTP do ciclo de vida.',
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
    return ServiceAuthContext(ator='service-token:test-lifecycle', via_token=True)


def test_helpers_resolvem_requisito_correlation_e_404(db_session):
    requisito = _requisito(db_session)

    assert api._correlation_id(' corr-123 ') == 'corr-123'
    assert api._correlation_id(None).startswith('lifecycle-')
    assert api._get_requirement(db_session, requisito.id).id == requisito.id
    assert api._get_requirement_by_code(db_session, ' REQ-246813579 ').id == requisito.id

    with pytest.raises(HTTPException) as exc_id:
        api._get_requirement(db_session, 999999)
    assert exc_id.value.status_code == 404

    with pytest.raises(HTTPException) as exc_code:
        api._get_requirement_by_code(db_session, 'REQ-000000000')
    assert exc_code.value.status_code == 404


def test_iniciar_lifecycle_encaminha_contexto_e_preserva_correlation(db_session, monkeypatch):
    requisito = _requisito(db_session, 'REQ-111222444')
    captured = {}

    def fake_start(db, **kwargs):
        captured.update(kwargs)
        return {'codigo': kwargs['requisito'].codigo, 'stages': {'requisito': True}}

    monkeypatch.setattr(api, 'start_lifecycle', fake_start)

    response = api.iniciar_lifecycle(
        requisito.id,
        payload=None,
        db=db_session,
        auth=_auth(),
        x_correlation_id='corr-start',
    )

    assert response['success'] is True
    assert response['meta']['correlation_id'] == 'corr-start'
    assert captured['requisito'].id == requisito.id
    assert captured['github_repo'] == 'ericson-j-santos/reqsys-v2-enterprise-real'
    assert captured['actor'] == 'service-token:test-lifecycle'


def test_iniciar_lifecycle_converte_erro_de_integracao_em_409(db_session, monkeypatch):
    requisito = _requisito(db_session, 'REQ-111222445')

    def fail_start(*_args, **_kwargs):
        raise api.LifecycleError('integração indisponível')

    monkeypatch.setattr(api, 'start_lifecycle', fail_start)

    with pytest.raises(HTTPException) as exc:
        api.iniciar_lifecycle(
            requisito.id,
            payload=api.LifecycleStartIn(github_repo='org/repo'),
            db=db_session,
            auth=_auth(),
            x_correlation_id='corr-fail',
        )
    assert exc.value.status_code == 409
    assert 'integração indisponível' in exc.value.detail


def test_consultas_por_id_e_codigo_retornam_snapshot(db_session, monkeypatch):
    requisito = _requisito(db_session, 'REQ-555666777')

    monkeypatch.setattr(
        api,
        'lifecycle_snapshot',
        lambda _db, req: {'codigo': req.codigo, 'progresso_percentual': 50.0},
    )

    by_id = api.consultar_lifecycle(
        requisito.id,
        db=db_session,
        _auth=_auth(),
        x_correlation_id='corr-id',
    )
    by_code = api.consultar_lifecycle_por_codigo(
        requisito.codigo,
        db=db_session,
        _auth=_auth(),
        x_correlation_id='corr-code',
    )

    assert by_id['data']['codigo'] == requisito.codigo
    assert by_id['meta']['correlation_id'] == 'corr-id'
    assert by_code['data']['codigo'] == requisito.codigo
    assert by_code['meta']['correlation_id'] == 'corr-code'


def test_registro_de_evidencia_por_id_e_codigo_e_erro_422(db_session, monkeypatch):
    requisito = _requisito(db_session, 'REQ-777888999')
    calls = []

    def fake_register(db, **kwargs):
        calls.append(kwargs)
        return {
            'codigo': kwargs['requisito'].codigo,
            'evidence': {
                'tipo': kwargs['tipo'],
                'referencia': kwargs['referencia'],
                'ambiente': kwargs['ambiente'],
            },
        }

    monkeypatch.setattr(api, 'register_lifecycle_evidence', fake_register)
    payload = api.LifecycleEvidenceIn(
        provedor='github',
        tipo='pr',
        repo='org/repo',
        referencia='1511',
        url='https://github.com/org/repo/pull/1511',
        titulo='PR do requisito',
    )

    by_id = api.registrar_evidencia_lifecycle(
        requisito.id,
        payload,
        db=db_session,
        auth=_auth(),
        x_correlation_id='corr-evidence-id',
    )
    by_code = api.registrar_evidencia_lifecycle_por_codigo(
        requisito.codigo,
        payload,
        db=db_session,
        auth=_auth(),
        x_correlation_id='corr-evidence-code',
    )

    assert by_id['data']['evidence']['referencia'] == '1511'
    assert by_code['data']['codigo'] == requisito.codigo
    assert len(calls) == 2
    assert calls[0]['actor'] == 'service-token:test-lifecycle'

    def fail_register(*_args, **_kwargs):
        raise api.LifecycleError('ambiente inválido')

    monkeypatch.setattr(api, 'register_lifecycle_evidence', fail_register)
    with pytest.raises(HTTPException) as exc:
        api.registrar_evidencia_lifecycle(
            requisito.id,
            payload,
            db=db_session,
            auth=_auth(),
            x_correlation_id='corr-invalid',
        )
    assert exc.value.status_code == 422
    assert 'ambiente inválido' in exc.value.detail
