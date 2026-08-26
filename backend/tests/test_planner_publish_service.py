"""Testes de serviço — publicação governada do Planner com idempotência (issue #32)."""

import asyncio
import os
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_DB_PATH = Path(__file__).parent / 'test_reqsys_planner_publish_service.db'
os.environ.setdefault('APP_ENV', 'test')
os.environ.setdefault('DATABASE_URL', f'sqlite:///{_DB_PATH.as_posix()}')
os.environ.setdefault('JWT_SECRET', 'reqsys-test-secret-with-minimum-safe-length')

from app.db import Base, SessionLocal, engine
from app.models.planner_publish_attempt import PlannerPublishAttempt
from app.services import hub_lowcode as hub_svc
from app.services import planner_publish as svc

# O engine/DATABASE_URL da app é um singleton de módulo (app/db.py) — se este
# arquivo não for o primeiro a importar app.db numa sessão pytest completa, o
# `os.environ.setdefault` acima é um no-op e os testes rodam contra o banco
# sqlite de QUALQUER outro arquivo de teste que tenha importado primeiro. Por
# isso todo identificador sensível a unicidade (source_id, idempotency_key)
# carrega um sufixo aleatório por execução — nunca depender de um db "limpo".
_RUN_ID = uuid.uuid4().hex[:10]


@pytest.fixture(scope='module', autouse=True)
def _setup_db():
    Base.metadata.create_all(bind=engine)
    yield


def _run(coro):
    return asyncio.run(coro)


def _payload(**overrides):
    base = {
        'plan_id': 'plan-1',
        'bucket_id': 'bucket-1',
        'title': 'Revisar contrato Planner',
        'description': 'Descricao de teste',
        'due_date': '2026-09-01',
        'priority': 'alta',
        'source_id': f'requisito:{_RUN_ID}-1234',
        'requester': 'tester@example.com',
    }
    base.update(overrides)
    return base


def _mock_webhook_ok(mock_client_cls, resposta=None):
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = resposta or {'task_id': 'planner-task-1'}
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client
    return mock_client


@patch('app.services.hub_lowcode.httpx.AsyncClient')
def test_publicar_tarefa_sucesso_primeira_vez(mock_client_cls):
    db = SessionLocal()
    try:
        hub_svc.salvar_planner_webhook_config(db, webhook_url='https://example.com/planner-hook')
        _mock_webhook_ok(mock_client_cls)

        resultado = _run(svc.publicar_tarefa_planner_governada(db, _payload(source_id=f'requisito:{_RUN_ID}-sucesso-1'), 'corr-1'))

        assert resultado['ok'] is True
        assert resultado['status'] == svc.STATUS_PUBLICADO
        assert resultado['planner_task_id'] == 'planner-task-1'
        assert resultado['attempt_id'] > 0

        chave, _ = svc.calcular_idempotency_key(_payload(source_id=f'requisito:{_RUN_ID}-sucesso-1'))
        assert resultado['idempotency_key'] == chave
    finally:
        db.close()


@patch('app.services.hub_lowcode.httpx.AsyncClient')
def test_publicar_tarefa_mesmo_payload_retorna_duplicado_sem_novo_post(mock_client_cls):
    db = SessionLocal()
    try:
        hub_svc.salvar_planner_webhook_config(db, webhook_url='https://example.com/planner-hook')
        mock_client = _mock_webhook_ok(mock_client_cls)

        payload = _payload(source_id=f'requisito:{_RUN_ID}-duplicado-1')
        primeiro = _run(svc.publicar_tarefa_planner_governada(db, payload, 'corr-2a'))
        segundo = _run(svc.publicar_tarefa_planner_governada(db, payload, 'corr-2b'))

        assert primeiro['status'] == svc.STATUS_PUBLICADO
        assert segundo['status'] == svc.STATUS_DUPLICADO
        assert segundo['ok'] is True
        assert segundo['attempt_id'] == primeiro['attempt_id']
        assert mock_client.post.await_count == 1
    finally:
        db.close()


@patch('app.services.hub_lowcode.httpx.AsyncClient')
def test_publicar_tarefa_payload_diferente_mesmo_source_id_gera_nova_tentativa(mock_client_cls):
    db = SessionLocal()
    try:
        hub_svc.salvar_planner_webhook_config(db, webhook_url='https://example.com/planner-hook')
        _mock_webhook_ok(mock_client_cls)

        primeiro = _run(svc.publicar_tarefa_planner_governada(
            db, _payload(source_id=f'requisito:{_RUN_ID}-distintos-1', title='Titulo A'), 'corr-3a'
        ))
        segundo = _run(svc.publicar_tarefa_planner_governada(
            db, _payload(source_id=f'requisito:{_RUN_ID}-distintos-1', title='Titulo B'), 'corr-3b'
        ))

        assert primeiro['idempotency_key'] != segundo['idempotency_key']
        assert primeiro['attempt_id'] != segundo['attempt_id']
        assert segundo['status'] == svc.STATUS_PUBLICADO
    finally:
        db.close()


def test_publicar_tarefa_webhook_nao_configurado():
    db = SessionLocal()
    try:
        hub_svc.salvar_planner_webhook_config(db, webhook_url='')
        resultado = _run(svc.publicar_tarefa_planner_governada(db, _payload(source_id=f'requisito:{_RUN_ID}-sem-webhook-1'), 'corr-4'))
        assert resultado['status'] == svc.STATUS_FALHOU_INTEGRACAO
        assert resultado['ok'] is False
    finally:
        db.close()


@patch('app.services.hub_lowcode.httpx.AsyncClient')
def test_publicar_tarefa_http_status_error_marca_falhou_integracao(mock_client_cls):
    import httpx

    db = SessionLocal()
    try:
        hub_svc.salvar_planner_webhook_config(db, webhook_url='https://example.com/planner-hook', webhook_key='segredo-webhook-123')

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        erro_http = httpx.HTTPStatusError('erro', request=MagicMock(), response=mock_resp)
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=erro_http)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        resultado = _run(svc.publicar_tarefa_planner_governada(db, _payload(source_id=f'requisito:{_RUN_ID}-http-erro-1'), 'corr-5'))

        assert resultado['status'] == svc.STATUS_FALHOU_INTEGRACAO
        assert 'segredo-webhook-123' not in (resultado['erro'] or '')
    finally:
        db.close()


def test_publicar_tarefa_prioridade_invalida_nao_persiste_tentativa():
    db = SessionLocal()
    try:
        total_antes = db.query(PlannerPublishAttempt).count()
        resultado = _run(svc.publicar_tarefa_planner_governada(
            db, _payload(source_id=f'requisito:{_RUN_ID}-prioridade-invalida-1', priority='inexistente'), 'corr-6'
        ))
        total_depois = db.query(PlannerPublishAttempt).count()

        assert resultado['status'] == svc.STATUS_FALHOU_VALIDACAO
        assert total_depois == total_antes
    finally:
        db.close()


@patch('app.services.hub_lowcode.httpx.AsyncClient')
def test_reprocessar_tentativa_falhou_integracao_sucesso(mock_client_cls):
    db = SessionLocal()
    try:
        hub_svc.salvar_planner_webhook_config(db, webhook_url='')
        falha = _run(svc.publicar_tarefa_planner_governada(db, _payload(source_id=f'requisito:{_RUN_ID}-reprocesso-1'), 'corr-7a'))
        assert falha['status'] == svc.STATUS_FALHOU_INTEGRACAO

        hub_svc.salvar_planner_webhook_config(db, webhook_url='https://example.com/planner-hook')
        _mock_webhook_ok(mock_client_cls)

        resultado = _run(svc.reprocessar_tentativa(db, falha['attempt_id'], 'corr-7b'))

        assert resultado['status'] == svc.STATUS_PUBLICADO
        attempt = db.get(PlannerPublishAttempt, falha['attempt_id'])
        assert attempt.tentativas == 2
    finally:
        db.close()


@patch('app.services.hub_lowcode.httpx.AsyncClient')
def test_reprocessar_tentativa_ja_publicada_rejeitada(mock_client_cls):
    db = SessionLocal()
    try:
        hub_svc.salvar_planner_webhook_config(db, webhook_url='https://example.com/planner-hook')
        mock_client = _mock_webhook_ok(mock_client_cls)

        sucesso = _run(svc.publicar_tarefa_planner_governada(db, _payload(source_id=f'requisito:{_RUN_ID}-ja-publicada-1'), 'corr-8a'))
        assert sucesso['status'] == svc.STATUS_PUBLICADO

        with pytest.raises(ValueError):
            _run(svc.reprocessar_tentativa(db, sucesso['attempt_id'], 'corr-8b'))

        assert mock_client.post.await_count == 1
    finally:
        db.close()


def test_reprocessar_tentativa_excede_limite():
    db = SessionLocal()
    try:
        attempt = PlannerPublishAttempt(
            idempotency_key=f'chave-limite-teste-{_RUN_ID}',
            payload_hash='hash-teste',
            correlation_id='corr-limite',
            source_id=f'requisito:{_RUN_ID}-limite-1',
            plan_id='plan-1', bucket_id='bucket-1', title='Titulo', description='',
            due_date='2026-09-01', priority='alta', requester='tester@example.com',
            status=svc.STATUS_FALHOU_INTEGRACAO,
            tentativas=svc.MAX_TENTATIVAS_REPROCESSO,
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)

        with pytest.raises(ValueError):
            _run(svc.reprocessar_tentativa(db, attempt.id, 'corr-limite-2'))
    finally:
        db.close()


def test_reprocessar_tentativa_inexistente():
    db = SessionLocal()
    try:
        with pytest.raises(ValueError):
            _run(svc.reprocessar_tentativa(db, 999999, 'corr-inexistente'))
    finally:
        db.close()
