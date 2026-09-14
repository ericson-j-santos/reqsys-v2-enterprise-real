from __future__ import annotations

import json

import pytest

from app.models.auditoria import AuditoriaEvento
from app.models.requisito import Requisito
from app.models.vinculo_git import VinculoGit
from app.services import redmine_lifecycle_sync as sync


def _requisito_com_redmine(db_session, codigo: str = 'REQ-168600001') -> Requisito:
    requisito = Requisito(
        codigo=codigo,
        titulo='Sincronização ReqSys Redmine',
        descricao='Critério de aceite: sincronizar sem loop e sem duplicidade entre ReqSys e Redmine.',
        urgencia='alta',
        area='Engenharia',
        sistema='ReqSys',
        solicitante='teste@reqsys.local',
        status='em_execucao',
        impacto_regulatorio=False,
    )
    db_session.add(requisito)
    db_session.flush()
    db_session.add(
        VinculoGit(
            requisito_codigo=requisito.codigo,
            requisito_id=requisito.id,
            tipo='issue',
            provedor='redmine',
            repo='redmine',
            referencia='9001',
            url='https://redmine.example/issues/9001',
            titulo='Redmine issue #9001',
            autor='tester',
        )
    )
    db_session.commit()
    db_session.refresh(requisito)
    return requisito


def _remote_issue(requisito: Requisito, *, atualizado: bool, journal_id: int = 10) -> dict:
    desired = sync.montar_campos_requisito_redmine(requisito)
    return {
        'id': 9001,
        'subject': desired['subject'] if atualizado else 'Título antigo',
        'description': desired['description'] if atualizado else 'Descrição antiga',
        'status': {'id': 2, 'name': 'In Progress'},
        'assigned_to': {'id': 7, 'name': 'Equipe Backend'},
        'done_ratio': 40,
        'journals': [
            {
                'id': journal_id,
                'user': {'id': 11, 'name': 'Operador Redmine'},
                'created_on': '2026-09-14T18:00:00Z',
                'notes': 'Implementação iniciada no Redmine.',
            }
        ],
    }


def test_sync_aplica_reqsys_importa_execucao_e_journal_com_confirmacao_independente(
    db_session,
    monkeypatch,
):
    requisito = _requisito_com_redmine(db_session)
    reads = [
        _remote_issue(requisito, atualizado=False),
        _remote_issue(requisito, atualizado=True),
    ]
    updates = []

    monkeypatch.setattr(
        sync,
        'obter_issue_redmine',
        lambda *_args, **_kwargs: reads.pop(0),
    )
    monkeypatch.setattr(
        sync,
        'atualizar_issue_redmine',
        lambda issue_id, campos: updates.append((issue_id, campos.copy())) or campos,
    )

    result = sync.sincronizar_requisito_redmine(
        db_session,
        requisito=requisito,
        correlation_id='corr-redmine-sync-001',
        actor='tester',
    )

    assert result['reqsys_to_redmine']['applied'] is True
    assert result['reqsys_to_redmine']['changed_fields'] == ['description', 'subject']
    assert result['redmine_to_reqsys']['execution'] == {
        'status_id': 2,
        'status_name': 'In Progress',
        'assignee_id': 7,
        'assignee_name': 'Equipe Backend',
        'done_ratio': 40,
    }
    assert result['redmine_to_reqsys']['new_journal_ids'] == [10]
    assert result['redmine_to_reqsys']['imported_comment_count'] == 1
    assert updates and updates[0][0] == 9001
    assert requisito.status == 'em_execucao'

    state_link = (
        db_session.query(VinculoGit)
        .filter(VinculoGit.requisito_id == requisito.id)
        .filter(VinculoGit.tipo == sync.SYNC_STATE_TYPE)
        .one()
    )
    state = json.loads(state_link.titulo)
    assert state['last_journal_id'] == 10
    assert state['execution']['status_name'] == 'In Progress'

    actions = {
        row.acao
        for row in db_session.query(AuditoriaEvento)
        .filter(AuditoriaEvento.entidade_id == str(requisito.id))
        .all()
    }
    assert 'REDMINE_SYNC_REQSYS_TO_REDMINE' in actions
    assert 'REDMINE_SYNC_REDMINE_TO_REQSYS' in actions
    assert 'REDMINE_JOURNAL_IMPORTADO' in actions


def test_sync_repetido_e_idempotente_sem_novas_mutacoes(db_session, monkeypatch):
    requisito = _requisito_com_redmine(db_session, 'REQ-168600002')
    remote = _remote_issue(requisito, atualizado=True)

    monkeypatch.setattr(sync, 'obter_issue_redmine', lambda *_args, **_kwargs: remote)
    update_calls = []
    monkeypatch.setattr(
        sync,
        'atualizar_issue_redmine',
        lambda issue_id, campos: update_calls.append((issue_id, campos)) or campos,
    )

    first = sync.sincronizar_requisito_redmine(
        db_session,
        requisito=requisito,
        correlation_id='corr-redmine-sync-first',
        actor='tester',
    )
    audit_count_before = (
        db_session.query(AuditoriaEvento)
        .filter(AuditoriaEvento.entidade_id == str(requisito.id))
        .count()
    )

    second = sync.sincronizar_requisito_redmine(
        db_session,
        requisito=requisito,
        correlation_id='corr-redmine-sync-second',
        actor='tester',
    )
    audit_count_after = (
        db_session.query(AuditoriaEvento)
        .filter(AuditoriaEvento.entidade_id == str(requisito.id))
        .count()
    )

    assert first['state_changed'] is True
    assert second['state_changed'] is False
    assert second['mutation_count'] == 0
    assert second['redmine_to_reqsys']['new_journal_ids'] == []
    assert update_calls == []
    assert audit_count_after == audit_count_before
    assert (
        db_session.query(VinculoGit)
        .filter(VinculoGit.requisito_id == requisito.id)
        .filter(VinculoGit.tipo == sync.SYNC_STATE_TYPE)
        .count()
        == 1
    )


def test_dry_run_calcula_diff_sem_mutar_redmine_ou_banco(db_session, monkeypatch):
    requisito = _requisito_com_redmine(db_session, 'REQ-168600003')
    remote = _remote_issue(requisito, atualizado=False)

    monkeypatch.setattr(sync, 'obter_issue_redmine', lambda *_args, **_kwargs: remote)

    def should_not_update(*_args, **_kwargs):
        raise AssertionError('dry-run não pode atualizar o Redmine')

    monkeypatch.setattr(sync, 'atualizar_issue_redmine', should_not_update)

    result = sync.sincronizar_requisito_redmine(
        db_session,
        requisito=requisito,
        correlation_id='corr-redmine-dry-run',
        actor='tester',
        dry_run=True,
    )

    assert result['dry_run'] is True
    assert result['reqsys_to_redmine']['planned'] is True
    assert result['reqsys_to_redmine']['applied'] is False
    assert result['mutation_count'] == 0
    assert (
        db_session.query(VinculoGit)
        .filter(VinculoGit.requisito_id == requisito.id)
        .filter(VinculoGit.tipo == sync.SYNC_STATE_TYPE)
        .count()
        == 0
    )
    assert (
        db_session.query(AuditoriaEvento)
        .filter(AuditoriaEvento.entidade_id == str(requisito.id))
        .count()
        == 0
    )


def test_sync_sem_vinculo_redmine_falha_fechado(db_session):
    requisito = Requisito(
        codigo='REQ-168600004',
        titulo='Sem vínculo Redmine',
        descricao='Critério de aceite: falhar fechado quando não existe issue vinculada.',
        urgencia='media',
        area='Engenharia',
        sistema='ReqSys',
        solicitante='teste@reqsys.local',
        status='em_execucao',
        impacto_regulatorio=False,
    )
    db_session.add(requisito)
    db_session.commit()

    with pytest.raises(sync.RedmineLifecycleSyncError, match='não possui vínculo'):
        sync.sincronizar_requisito_redmine(
            db_session,
            requisito=requisito,
            correlation_id='corr-redmine-no-link',
            actor='tester',
        )


def test_sync_detecta_falso_positivo_quando_put_nao_persiste(db_session, monkeypatch):
    requisito = _requisito_com_redmine(db_session, 'REQ-168600005')
    stale = _remote_issue(requisito, atualizado=False)

    monkeypatch.setattr(sync, 'obter_issue_redmine', lambda *_args, **_kwargs: stale)
    monkeypatch.setattr(sync, 'atualizar_issue_redmine', lambda _id, campos: campos)

    with pytest.raises(sync.RedmineLifecycleSyncError, match='leitura independente'):
        sync.sincronizar_requisito_redmine(
            db_session,
            requisito=requisito,
            correlation_id='corr-redmine-false-positive',
            actor='tester',
        )
