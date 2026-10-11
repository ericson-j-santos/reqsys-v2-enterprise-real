import json
from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.ai_conversation_teams_observability import (
    construir_snapshot_teams_inbound,
    obter_snapshot_teams_inbound,
)


def _event(action, payload, *, created_at=None):
    return SimpleNamespace(
        acao=action,
        payload_minimo=json.dumps(payload),
        criado_em=created_at or datetime(2026, 10, 9, 15, 0, tzinfo=timezone.utc),
    )


def test_snapshot_saudavel_expoe_apenas_metricas_sanitizadas():
    snapshot = construir_snapshot_teams_inbound(
        [
            _event(
                'AI_CONVERSATION_TEAMS_MESSAGE_COMPLETED',
                {
                    'channel': 'teams_bot',
                    'duplicate': False,
                    'response_sent': True,
                    'latency_ms': 2994,
                },
            ),
            _event(
                'AI_CONVERSATION_TEAMS_MESSAGE_COMPLETED',
                {
                    'channel': 'teams_bot',
                    'duplicate': True,
                    'response_sent': False,
                    'latency_ms': 100,
                },
            ),
        ],
        window_minutes=15,
    )

    assert snapshot['status'] == 'healthy'
    assert snapshot['alert_required'] is False
    assert snapshot['metrics']['total'] == 2
    assert snapshot['metrics']['duplicates'] == 1
    assert snapshot['metrics']['responses_sent'] == 1
    assert snapshot['metrics']['latency_average_ms'] == 1547
    assert snapshot['privacy'] == {
        'message_content_included': False,
        'user_identity_included': False,
        'provider_response_included': False,
    }
    assert 'mensagem' not in json.dumps(snapshot)


def test_snapshot_contabiliza_reply_completed_e_replay_sem_segunda_resposta():
    snapshot = construir_snapshot_teams_inbound(
        [
            _event(
                'AI_CONVERSATION_TEAMS_REPLY_COMPLETED',
                {
                    'channel': 'teams_bot',
                    'duplicate': False,
                    'response_sent': True,
                    'latency_ms': 200,
                },
            ),
            _event(
                'AI_CONVERSATION_TEAMS_REPLY_COMPLETED',
                {
                    'channel': 'teams_bot',
                    'duplicate': True,
                    'response_sent': False,
                    'latency_ms': 50,
                },
            ),
        ],
        window_minutes=15,
    )

    assert snapshot['status'] == 'healthy'
    assert snapshot['metrics']['total'] == 2
    assert snapshot['metrics']['completed'] == 2
    assert snapshot['metrics']['duplicates'] == 1
    assert snapshot['metrics']['responses_sent'] == 1


def test_consulta_inbound_inclui_reply_completed_no_filtro_de_acoes():
    class FakeQuery:
        def __init__(self):
            self.criteria = ()

        def filter(self, *criteria):
            self.criteria = criteria
            return self

        def order_by(self, *_args):
            return self

        def limit(self, _limit):
            return self

        def all(self):
            return []

    class FakeDb:
        def __init__(self):
            self.query_obj = FakeQuery()

        def query(self, _model):
            return self.query_obj

    db = FakeDb()
    snapshot = obter_snapshot_teams_inbound(
        db,
        window_minutes=15,
        now=datetime(2026, 10, 9, 15, 0, tzinfo=timezone.utc),
    )

    actions_clause = db.query_obj.criteria[1]
    assert 'AI_CONVERSATION_TEAMS_REPLY_COMPLETED' in actions_clause.right.value
    assert snapshot['metrics']['total'] == 0


def test_snapshot_degradado_quando_taxa_de_falha_atinge_limite():
    completed = _event(
        'AI_CONVERSATION_TEAMS_MESSAGE_COMPLETED',
        {'channel': 'teams_bot', 'latency_ms': 200, 'response_sent': True},
    )
    failed = _event(
        'AI_CONVERSATION_TEAMS_MESSAGE_FAILED',
        {'channel': 'teams_bot', 'latency_ms': 300, 'error_category': 'RuntimeError'},
    )

    snapshot = construir_snapshot_teams_inbound(
        [completed, completed, completed, completed, failed],
        window_minutes=15,
    )

    assert snapshot['status'] == 'degraded'
    assert snapshot['alert_required'] is True
    assert snapshot['metrics']['failure_rate_percent'] == 20.0
    assert snapshot['alerts'] == ['teams_inbound_failure_rate_high']


def test_snapshot_sem_eventos_retorna_unknown_sem_falso_alerta():
    snapshot = construir_snapshot_teams_inbound([], window_minutes=15)

    assert snapshot['status'] == 'unknown'
    assert snapshot['alert_required'] is False
    assert snapshot['metrics']['total'] == 0


def test_snapshot_ignora_evento_de_outro_canal_e_payload_invalido():
    snapshot = construir_snapshot_teams_inbound(
        [
            _event(
                'AI_CONVERSATION_TEAMS_MESSAGE_COMPLETED',
                {'channel': 'outro', 'latency_ms': 10},
            ),
            SimpleNamespace(
                acao='AI_CONVERSATION_TEAMS_MESSAGE_COMPLETED',
                payload_minimo='{invalido',
                criado_em=datetime.now(timezone.utc),
            ),
        ],
        window_minutes=15,
    )

    assert snapshot['metrics']['total'] == 0
