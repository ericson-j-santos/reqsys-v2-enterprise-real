"""Testes da memória persistente Planner/Excel/Copilot (#1359)."""

import os
import uuid
from pathlib import Path

import pytest

_DB_PATH = Path(__file__).parent / 'test_reqsys_copilot_memory_service.db'
os.environ.setdefault('APP_ENV', 'test')
os.environ.setdefault('DATABASE_URL', f'sqlite:///{_DB_PATH.as_posix()}')
os.environ.setdefault('JWT_SECRET', 'reqsys-test-secret-with-minimum-safe-length')

from app.db import Base, SessionLocal, engine
from app.models.copilot_memory import CopilotMemoryHistory, CopilotMemoryRecord
from app.services import copilot_memory as svc

_RUN_ID = uuid.uuid4().hex[:10]


@pytest.fixture(scope='module', autouse=True)
def _setup_db():
    Base.metadata.create_all(bind=engine)
    yield


def _planner_payload(task_id: str, **overrides):
    base = {
        'planner_task_id': task_id,
        'origem': 'planner',
        'planner_titulo': 'Validar memória do Copilot',
        'planner_status': 'em_andamento',
        'planner_percentual': 25,
        'planner_prazo': '2026-09-10',
    }
    base.update(overrides)
    return base


def test_planner_cria_memoria_e_historico():
    db = SessionLocal()
    task_id = f'planner-{_RUN_ID}-01'
    try:
        resultado = svc.sincronizar_item(db, _planner_payload(task_id), 'corr-01')

        assert resultado['changed'] is True
        assert resultado['versao'] == 1
        assert resultado['plannerTaskId'] == task_id
        assert resultado['plannerSyncStatus'] == svc.STATUS_SINCRONIZADO
        assert resultado['assunto'] == 'Validar memória do Copilot'

        historico = db.query(CopilotMemoryHistory).filter(
            CopilotMemoryHistory.memory_id == resultado['memoryId']
        ).all()
        assert len(historico) == 1
    finally:
        db.close()


def test_mesmo_payload_planner_e_idempotente():
    db = SessionLocal()
    task_id = f'planner-{_RUN_ID}-02'
    try:
        primeiro = svc.sincronizar_item(db, _planner_payload(task_id), 'corr-02a')
        segundo = svc.sincronizar_item(db, _planner_payload(task_id), 'corr-02b')

        assert primeiro['changed'] is True
        assert segundo['changed'] is False
        assert segundo['versao'] == 1

        total_historico = db.query(CopilotMemoryHistory).filter(
            CopilotMemoryHistory.memory_id == primeiro['memoryId']
        ).count()
        assert total_historico == 1
    finally:
        db.close()


def test_excel_solicita_atualizacao_planner_sem_loop():
    db = SessionLocal()
    task_id = f'planner-{_RUN_ID}-03'
    try:
        inicial = svc.sincronizar_item(db, _planner_payload(task_id), 'corr-03a')
        memoria_id = inicial['memoryId']
        old_hash = inicial['plannerAppliedHash']

        alterado = svc.sincronizar_item(db, {
            'memory_id': memoria_id,
            'planner_task_id': task_id,
            'origem': 'excel',
            'planner_titulo': 'Validar memória persistente - revisado',
            'atualizar_planner': True,
        }, 'corr-03b')

        assert alterado['changed'] is True
        assert alterado['versao'] == 2
        assert alterado['plannerSyncStatus'] == svc.STATUS_PENDENTE
        assert alterado['atualizarPlanner'] is True
        assert alterado['plannerAppliedHash'] == old_hash

        comandos = svc.listar_comandos_planner(db)
        comando = next(item for item in comandos if item['memoryId'] == memoria_id)
        assert comando['plannerTitulo'] == 'Validar memória persistente - revisado'

        # Planner ainda refletindo o estado anterior deve ser tratado como eco,
        # sem apagar a alteração local e sem criar nova versão.
        eco = svc.sincronizar_item(db, _planner_payload(task_id), 'corr-03c')
        assert eco['changed'] is False
        assert eco['versao'] == 2
        assert eco['plannerSyncStatus'] == svc.STATUS_PENDENTE
        assert eco['plannerTitulo'] == 'Validar memória persistente - revisado'

        confirmado = svc.confirmar_comando_planner(
            db,
            memoria_id,
            sucesso=True,
            correlation_id='corr-03d',
            planner_task_id=task_id,
        )
        assert confirmado['plannerSyncStatus'] == svc.STATUS_SINCRONIZADO
        assert confirmado['atualizarPlanner'] is False
        assert not any(item['memoryId'] == memoria_id for item in svc.listar_comandos_planner(db))
    finally:
        db.close()


def test_atualizacao_apenas_de_memoria_nao_gera_comando_planner():
    db = SessionLocal()
    task_id = f'planner-{_RUN_ID}-04'
    try:
        inicial = svc.sincronizar_item(db, _planner_payload(task_id), 'corr-04a')
        alterado = svc.sincronizar_item(db, {
            'memory_id': inicial['memoryId'],
            'planner_task_id': task_id,
            'origem': 'excel',
            'contexto': 'Pesquisa validada e persistida no ReqSys.',
            'decisao': 'Manter Planner como fonte operacional.',
            'atualizar_planner': False,
        }, 'corr-04b')

        assert alterado['changed'] is True
        assert alterado['versao'] == 2
        assert alterado['atualizarPlanner'] is False
        assert alterado['plannerSyncStatus'] == svc.STATUS_SINCRONIZADO
        assert not any(item['memoryId'] == inicial['memoryId'] for item in svc.listar_comandos_planner(db))
    finally:
        db.close()


def test_alteracao_concorrente_no_planner_vira_conflito_fail_closed():
    db = SessionLocal()
    task_id = f'planner-{_RUN_ID}-05'
    try:
        inicial = svc.sincronizar_item(db, _planner_payload(task_id), 'corr-05a')
        memoria_id = inicial['memoryId']

        local = svc.sincronizar_item(db, {
            'memory_id': memoria_id,
            'planner_task_id': task_id,
            'origem': 'excel',
            'planner_titulo': 'Título solicitado pelo Excel',
            'atualizar_planner': True,
        }, 'corr-05b')
        assert local['plannerSyncStatus'] == svc.STATUS_PENDENTE

        remoto = svc.sincronizar_item(db, _planner_payload(
            task_id,
            planner_titulo='Título alterado diretamente no Planner',
            planner_percentual=50,
        ), 'corr-05c')

        assert remoto['changed'] is False
        assert remoto['plannerSyncStatus'] == svc.STATUS_CONFLITO
        assert remoto['plannerTitulo'] == 'Título solicitado pelo Excel'
        assert 'revisão necessária' in remoto['ultimoErro']
    finally:
        db.close()


def test_ack_falha_mantem_rastreabilidade_e_permitem_nova_solicitacao():
    db = SessionLocal()
    task_id = f'planner-{_RUN_ID}-06'
    try:
        inicial = svc.sincronizar_item(db, _planner_payload(task_id), 'corr-06a')
        memoria_id = inicial['memoryId']
        svc.sincronizar_item(db, {
            'memory_id': memoria_id,
            'planner_task_id': task_id,
            'origem': 'excel',
            'planner_percentual': 75,
            'atualizar_planner': True,
        }, 'corr-06b')

        falha = svc.confirmar_comando_planner(
            db,
            memoria_id,
            sucesso=False,
            correlation_id='corr-06c',
            erro='Planner indisponível',
        )
        assert falha['plannerSyncStatus'] == svc.STATUS_ERRO
        assert falha['atualizarPlanner'] is True
        assert falha['ultimoErro'] == 'Planner indisponível'

        rearmado = svc.sincronizar_item(db, {
            'memory_id': memoria_id,
            'planner_task_id': task_id,
            'origem': 'excel',
            'planner_percentual': 75,
            'atualizar_planner': True,
        }, 'corr-06d')
        assert rearmado['changed'] is False
        assert rearmado['plannerSyncStatus'] == svc.STATUS_PENDENTE
    finally:
        db.close()
