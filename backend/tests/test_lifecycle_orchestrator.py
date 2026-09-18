from __future__ import annotations

import pytest

from app.models.requisito import Requisito
from app.models.vinculo_git import VinculoGit
from app.services import lifecycle_orchestrator as lifecycle


def _requisito(db_session, codigo: str = 'REQ-123456789') -> Requisito:
    requisito = Requisito(
        codigo=codigo,
        titulo='Sincronizar requisito ponta a ponta',
        descricao='Critério de aceite: rastrear Redmine, GitHub, PR e deploy sem duplicidade.',
        urgencia='alta',
        area='Engenharia',
        sistema='ReqSys',
        solicitante='teste@reqsys.local',
        status='estruturado',
        impacto_regulatorio=False,
    )
    db_session.add(requisito)
    db_session.commit()
    db_session.refresh(requisito)
    return requisito


def test_start_lifecycle_e_idempotente_sem_alterar_estado_canonico(db_session, monkeypatch):
    requisito = _requisito(db_session)
    calls = {'redmine': 0, 'github': 0}

    def fake_redmine(**_kwargs):
        calls['redmine'] += 1
        return {
            'issue_principal_id': 9001,
            'redmine_url': 'https://redmine.example/issues/9001',
            'subtarefas': [],
            'warnings': [],
        }

    def fake_github(**_kwargs):
        calls['github'] += 1
        return {
            'issue_number': 1511,
            'github_url': 'https://github.com/org/repo/issues/1511',
            'title': '[REQ-123456789] Sincronizar requisito ponta a ponta',
            'created': True,
        }

    monkeypatch.setattr(lifecycle, 'publish_requisito_to_redmine', fake_redmine)
    monkeypatch.setattr(lifecycle, 'find_or_create_requirement_issue', fake_github)

    first = lifecycle.start_lifecycle(
        db_session,
        requisito=requisito,
        github_repo='org/repo',
        correlation_id='corr-lifecycle-001',
        actor='tester',
    )
    second = lifecycle.start_lifecycle(
        db_session,
        requisito=requisito,
        github_repo='org/repo',
        correlation_id='corr-lifecycle-002',
        actor='tester',
    )

    assert calls == {'redmine': 1, 'github': 1}
    assert requisito.status == 'estruturado'
    assert first['status_requisito'] == 'estruturado'
    assert first['stages']['redmine'] is True
    assert first['stages']['github_issue'] is True
    assert second['stages']['redmine'] is True
    assert second['stages']['github_issue'] is True

    links = db_session.query(VinculoGit).filter(VinculoGit.requisito_id == requisito.id).all()
    assert len(links) == 2
    assert {(link.provedor, link.tipo, link.referencia) for link in links} == {
        ('redmine', 'issue', '9001'),
        ('github', 'issue', '1511'),
    }


def test_register_evidence_consolida_pr_commit_e_deploy_sem_transicionar(db_session):
    requisito = _requisito(db_session, 'REQ-987654321')
    requisito.status = 'em_execucao'
    db_session.commit()

    lifecycle.register_lifecycle_evidence(
        db_session,
        requisito=requisito,
        provedor='github',
        tipo='pr',
        repo='org/repo',
        referencia='1512',
        url='https://github.com/org/repo/pull/1512',
        titulo='PR do requisito',
        ambiente=None,
        correlation_id='corr-pr',
        actor='github-actions',
    )
    duplicate = lifecycle.register_lifecycle_evidence(
        db_session,
        requisito=requisito,
        provedor='github',
        tipo='pr',
        repo='org/repo',
        referencia='1512',
        url='https://github.com/org/repo/pull/1512',
        titulo='PR do requisito atualizada',
        ambiente=None,
        correlation_id='corr-pr-duplicate',
        actor='github-actions',
    )
    lifecycle.register_lifecycle_evidence(
        db_session,
        requisito=requisito,
        provedor='github',
        tipo='commit',
        repo='org/repo',
        referencia='abc123',
        url='https://github.com/org/repo/commit/abc123',
        titulo='Commit integrado',
        ambiente=None,
        correlation_id='corr-commit',
        actor='github-actions',
    )

    for environment in ('dev', 'staging', 'prod'):
        lifecycle.register_lifecycle_evidence(
            db_session,
            requisito=requisito,
            provedor='fly',
            tipo='deploy',
            repo='reqsys-api',
            referencia=f'abc123-{environment}',
            url=f'https://reqsys-{environment}.example/health',
            titulo=f'Deploy {environment}',
            ambiente=environment,
            correlation_id=f'corr-{environment}',
            actor='github-actions',
        )

    snapshot = lifecycle.lifecycle_snapshot(db_session, requisito)

    assert duplicate['evidence_created'] is False
    assert snapshot['stages']['pull_request'] is True
    assert snapshot['stages']['commit'] is True
    assert snapshot['stages']['deploy_dev'] is True
    assert snapshot['stages']['deploy_staging'] is True
    assert snapshot['stages']['deploy_prod'] is True
    assert snapshot['ready_for_explicit_completion'] is True
    assert requisito.status == 'em_execucao'

    pr_links = (
        db_session.query(VinculoGit)
        .filter(VinculoGit.requisito_id == requisito.id)
        .filter(VinculoGit.provedor == 'github')
        .filter(VinculoGit.tipo == 'pr')
        .all()
    )
    assert len(pr_links) == 1
    assert pr_links[0].titulo == 'PR do requisito atualizada'


def test_deploy_rejeita_ambiente_desconhecido(db_session):
    requisito = _requisito(db_session, 'REQ-111222333')

    with pytest.raises(lifecycle.LifecycleError, match='dev, staging ou prod'):
        lifecycle.register_lifecycle_evidence(
            db_session,
            requisito=requisito,
            provedor='fly',
            tipo='deploy',
            repo='reqsys-api',
            referencia='abc123-unknown',
            ambiente='qa-invalido',
            correlation_id='corr-invalid',
            actor='tester',
        )


def test_start_lifecycle_rejeita_requisito_terminal(db_session):
    requisito = _requisito(db_session, 'REQ-444555666')
    requisito.status = 'exportado'
    db_session.commit()

    with pytest.raises(lifecycle.LifecycleError, match='estado terminal'):
        lifecycle.start_lifecycle(
            db_session,
            requisito=requisito,
            github_repo='org/repo',
            correlation_id='corr-terminal',
            actor='tester',
        )
