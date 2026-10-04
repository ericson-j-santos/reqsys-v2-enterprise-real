from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.encrypted_text import decrypt_text, encrypt_text
from app.db import Base
from app.models.ai_conversation import AIConversation, AIUsageLedger
from app.services.ai_conversation import _classification_lock, executar_turno
from app.services.ai_history_protection import (
    DEFAULT_AI_CONVERSATION_RETENTION_DAYS,
    AIHistoryProtectionError,
    AIScopeViolationError,
    AIUsageBudgetExceededError,
    assert_budget,
    assert_scope,
    delete_conversation,
    estimate_tokens,
    purge_expired_conversations,
    record_usage,
    retention_days,
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
        assert_scope(conversation, tenant_id='tenant-b', area_id='juridico', enforce=True)
    with pytest.raises(AIScopeViolationError, match='área'):
        assert_scope(conversation, tenant_id='tenant-a', area_id='financeiro', enforce=True)


def test_estimativa_de_tokens_e_explicitamente_estimativa() -> None:
    assert estimate_tokens('12345678') == 2
    assert estimate_tokens('') == 1


def _db():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _conversation(db, *, conversation_id: str = 'conv-budget') -> AIConversation:
    conversation = AIConversation(
        id=conversation_id,
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
        classification_lock_sha256=_classification_lock(conversation_id, 'internal'),
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
        assert_budget(db, conversation=conversation, estimated_next_tokens=21, env=env)


def test_executar_turno_mascara_pii_antes_do_gateway(monkeypatch) -> None:
    monkeypatch.setenv('AI_CONVERSATION_ENCRYPTION_MODE', 'off')
    db = _db()
    conversation = _conversation(db, conversation_id='conv-mask')

    class GatewayFake:
        prompt_recebido = ''

        def gerar_ollama(self, **kwargs):
            self.prompt_recebido = kwargs['prompt']
            return 'resposta segura'

    gateway = GatewayFake()
    executar_turno(
        db,
        conversa=conversation,
        mensagem='Meu CPF é 123.456.789-01 e e-mail ericson@example.com',
        correlation_id='corr-mask',
        idempotency_key='mask-1',
        origem='test',
        enviar_teams=False,
        gateway=gateway,
        env={
            'AI_CORPORATE_POLICY_MODE': 'off',
            'AI_CONVERSATION_OLLAMA_BASE_URL': 'http://localhost:11434',
            'AI_CONVERSATION_PII_MASKING': 'true',
        },
    )
    assert '123.456.789-01' not in gateway.prompt_recebido
    assert 'ericson@example.com' not in gateway.prompt_recebido
    assert '[DADO_MASCARADO]' in gateway.prompt_recebido


def test_retention_days_usa_default_e_aceita_valor_customizado() -> None:
    assert retention_days(None) == DEFAULT_AI_CONVERSATION_RETENTION_DAYS
    assert retention_days({'AI_CONVERSATION_RETENTION_DAYS': '10'}) == 10


def test_retention_days_rejeita_valor_nao_numerico() -> None:
    with pytest.raises(AIHistoryProtectionError, match='inválido'):
        retention_days({'AI_CONVERSATION_RETENTION_DAYS': 'abc'})


def test_retention_days_rejeita_valor_menor_que_um() -> None:
    with pytest.raises(AIHistoryProtectionError, match='pelo menos 1 dia'):
        retention_days({'AI_CONVERSATION_RETENTION_DAYS': '0'})


def test_escopo_enforce_sem_tenant_id_bloqueia() -> None:
    conversation = SimpleNamespace(tenant_id='tenant-a', area_id='ti')
    with pytest.raises(AIScopeViolationError, match='X-Tenant-ID'):
        assert_scope(conversation, tenant_id=None, area_id=None, enforce=True)


def test_escopo_permite_quando_tenant_e_area_coincidem_ou_nao_sao_exigidos() -> None:
    conversation = SimpleNamespace(tenant_id='tenant-a', area_id='ti')
    assert_scope(conversation, tenant_id='tenant-a', area_id='ti', enforce=True)
    assert_scope(conversation, tenant_id=None, area_id=None, enforce=False)


def test_orcamento_rejeita_budgets_json_invalido() -> None:
    db = _db()
    conversation = _conversation(db, conversation_id='conv-budget-invalido')
    env = {'AI_REQUESTER_MONTHLY_TOKEN_BUDGETS_JSON': 'não-é-json'}
    with pytest.raises(AIHistoryProtectionError, match='JSON objeto'):
        assert_budget(db, conversation=conversation, estimated_next_tokens=1, env=env)


def test_orcamento_rejeita_budgets_json_que_nao_e_objeto() -> None:
    db = _db()
    conversation = _conversation(db, conversation_id='conv-budget-lista')
    env = {'AI_COST_CENTER_MONTHLY_TOKEN_BUDGETS_JSON': '[1, 2, 3]'}
    with pytest.raises(AIHistoryProtectionError, match='JSON objeto'):
        assert_budget(db, conversation=conversation, estimated_next_tokens=1, env=env)


def test_orcamento_por_solicitante_bloqueia_antes_do_excesso() -> None:
    db = _db()
    conversation = _conversation(db, conversation_id='conv-budget-solicitante')
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
    env = {'AI_REQUESTER_MONTHLY_TOKEN_BUDGETS_JSON': '{"user-1": 100}'}
    with pytest.raises(AIUsageBudgetExceededError, match='solicitante'):
        assert_budget(db, conversation=conversation, estimated_next_tokens=21, env=env)


def test_purge_expired_conversations_remove_apenas_vencidas_do_tenant() -> None:
    db = _db()
    agora = datetime.now(UTC)
    vencida = _conversation(db, conversation_id='conv-vencida')
    vencida.atualizado_em = agora - timedelta(days=90)
    recente = _conversation(db, conversation_id='conv-recente')
    recente.atualizado_em = agora
    db.commit()

    resultado = purge_expired_conversations(
        db,
        env={'AI_CONVERSATION_RETENTION_DAYS': '30'},
        tenant_id='tenant-a',
        now=agora,
    )

    assert resultado['registros_removidos'] == 1
    assert resultado['retention_days'] == 30
    assert db.get(AIConversation, 'conv-vencida') is None
    assert db.get(AIConversation, 'conv-recente') is not None


def test_purge_expired_conversations_sem_correspondencia_retorna_zero() -> None:
    db = _db()
    recente = _conversation(db, conversation_id='conv-ainda-valida')
    recente.atualizado_em = datetime.now(UTC)
    db.commit()

    resultado = purge_expired_conversations(db, env={'AI_CONVERSATION_RETENTION_DAYS': '30'})

    assert resultado['registros_removidos'] == 0
    assert db.get(AIConversation, 'conv-ainda-valida') is not None


def test_delete_conversation_remove_registro() -> None:
    db = _db()
    conversation = _conversation(db, conversation_id='conv-para-apagar')
    delete_conversation(db, conversation)
    assert db.get(AIConversation, 'conv-para-apagar') is None
