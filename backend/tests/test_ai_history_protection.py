from __future__ import annotations

import base64
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.encrypted_text import decrypt_text, encrypt_text
from app.db import Base
from app.models.ai_conversation import AIConversation, AIUsageLedger
from app.services.ai_history_protection import (
    AIScopeViolationError,
    AIUsageBudgetExceededError,
    assert_budget,
    assert_scope,
    estimate_tokens,
    record_usage,
)


def test_criptografia_round_trip_em_enforce(monkeypatch) -> None:
    key = base64.b64encode(b'k' * 32).decode('ascii')
    monkeypatch.setenv('AI_CONVERSATION_ENCRYPTION_MODE', 'enforce')
    monkeypatch.setenv('AI_CONVERSATION_CONTENT_ENCRYPTION_KEY_B64', key)
    encrypted = encrypt_text('conteúdo confidencial')
    assert encrypted.startswith('enc:v1:')
    assert 'confidencial' not in encrypted
    assert decrypt_text(encrypted) == 'conteúdo confidencial'


def test_legado_plaintext_continua_legivel(monkeypatch) -> None:
    monkeypatch.setenv('AI_CONVERSATION_ENCRYPTION_MODE', 'enforce')
    assert decrypt_text('registro-legado') == 'registro-legado'


def test_escopo_bloqueia_tenant_e_area_divergentes() -> None:
    conversation = SimpleNamespace(tenant_id='tenant-a', area_id='juridico')
    with pytest.raises(AIScopeViolationError, match='tenant'):
        assert_scope(
            conversation,
            tenant_id='tenant-b',
            area_id='juridico',
            enforce=True,
        )
    with pytest.raises(AIScopeViolationError, match='área'):
        assert_scope(
            conversation,
            tenant_id='tenant-a',
            area_id='financeiro',
            enforce=True,
        )


def test_estimativa_de_tokens_e_explicitamente_estimativa() -> None:
    assert estimate_tokens('12345678') == 2
    assert estimate_tokens('') == 1


def _db():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _conversation(db) -> AIConversation:
    conversation = AIConversation(
        id='conv-budget',
        provider='ollama',
        model='local',
        titulo='Teste',
        origem='test',
        status='aguardando_usuario',
        correlation_id='corr',
        tenant_id='tenant-a',
        area_id='ti',
        requester_id='user-1',
        cost_center='CC-10',
        data_classification='internal',
        classification_lock_sha256='0' * 64,
        requested_provider='ollama',
        authorized_provider='ollama',
        policy_mode='off',
        policy_decision='allowed',
        policy_reason='test',
        policy_correlation_id='corr',
        teams_destino_tipo='auto',
        teams_modo='auto',
        teams_permitir_fallback=True,
    )
    db.add(conversation)
    db.commit()
    return conversation


def test_ledger_registra_dimensoes_de_custo() -> None:
    db = _db()
    conversation = _conversation(db)
    ledger = record_usage(
        db,
        conversation=conversation,
        prompt='abcd' * 10,
        response='resposta',
        correlation_id='corr-2',
    )
    assert ledger.tenant_id == 'tenant-a'
    assert ledger.requester_id == 'user-1'
    assert ledger.cost_center == 'CC-10'
    assert ledger.total_estimated_tokens > 0


def test_orcamento_por_centro_de_custo_bloqueia_antes_do_excesso() -> None:
    db = _db()
    conversation = _conversation(db)
    db.add(
        AIUsageLedger(
            conversation_id=conversation.id,
            tenant_id=conversation.tenant_id,
            requester_id=conversation.requester_id,
            cost_center=conversation.cost_center,
            provider='ollama',
            model='local',
            correlation_id='old',
            estimated_input_tokens=30,
            estimated_output_tokens=50,
            total_estimated_tokens=80,
            criado_em=datetime.now(UTC),
        )
    )
    db.commit()
    env = {'AI_COST_CENTER_MONTHLY_TOKEN_BUDGETS_JSON': '{"CC-10": 100}'}
    with pytest.raises(AIUsageBudgetExceededError, match='centro de custo'):
        assert_budget(
            db,
            conversation=conversation,
            estimated_next_tokens=21,
            env=env,
        )
