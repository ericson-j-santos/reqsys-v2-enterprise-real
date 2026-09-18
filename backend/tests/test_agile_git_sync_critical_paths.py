"""Testes de caminhos críticos — sincronização Agile via Git."""

from time import time_ns

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.agile_runtime import AgileWorkItem
from app.services.agile_git_sync import sincronizar_work_items_git


def _db_session():
    engine = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def test_sincronizar_ignora_evento_sem_codigo():
    db = _db_session()
    try:
        assert sincronizar_work_items_git(db, [{'tipo': 'push', 'repo': 'o/r'}]) == []
    finally:
        db.close()


def test_sincronizar_atualiza_work_item_e_cria_evidencia():
    db = _db_session()
    codigo = f'AGI-SYNC-{time_ns()}'
    try:
        item = AgileWorkItem(
            codigo=codigo,
            tipo='story',
            titulo='Sync git',
            descricao='Item para webhook agile',
            prioridade='P2',
            pontos=2,
            valor_negocio=10,
            score_risco=5,
            owner_ai='qa-ia',
            status='em_execucao',
        )
        db.add(item)
        db.commit()

        ids = sincronizar_work_items_git(
            db,
            [
                {
                    'work_item_codigo': codigo,
                    'tipo': 'pr',
                    'provedor': 'github',
                    'repo': 'org/repo',
                    'branch': 'feature/sync',
                    'referencia': '42',
                    'url': 'https://github.com/org/repo/pull/42',
                    'ambiente': 'dev',
                    'pr_merged': True,
                    'autor': 'dev@example.com',
                }
            ],
        )

        assert ids == [item.id]
        db.refresh(item)
        assert item.branch == 'feature/sync'
        assert item.change_id == '42'
        assert item.status == 'em_ci'
        assert item.ambiente_deploy == 'dev'
    finally:
        db.close()


def test_sincronizar_merge_request_gitlab():
    db = _db_session()
    codigo = f'AGI-SYNC-{time_ns()}'
    try:
        item = AgileWorkItem(
            codigo=codigo,
            tipo='story',
            titulo='Sync gitlab',
            descricao='MR GitLab sync test',
            prioridade='P3',
            pontos=1,
            valor_negocio=5,
            score_risco=2,
            owner_ai='qa-ia',
            status='em_revisao',
        )
        db.add(item)
        db.commit()

        sincronizar_work_items_git(
            db,
            [
                {
                    'work_item_codigo': codigo.lower(),
                    'tipo': 'merge_request',
                    'provedor': 'gitlab',
                    'repo': 'grupo/proj',
                    'referencia': '7',
                    'url': 'https://gitlab.com/grupo/proj/-/merge_requests/7',
                    'mr_merged': True,
                }
            ],
        )

        db.refresh(item)
        assert item.change_provider == 'gitlab'
        assert item.ci_status == 'pending'
    finally:
        db.close()
