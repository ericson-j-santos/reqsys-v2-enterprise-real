"""Testes da tabela de decisão de readiness do monitoramento operacional."""

from app.api.monitoramento_operacional import _runtime_readiness_reason, _runtime_ready


def _snapshot(*, blocked_items: int = 0, status: str = 'healthy') -> dict:
    return {
        'critical_counts': {'blocked_items': blocked_items},
        'evidence': {'deploy_gate_relaxed': False},
        'status': status,
    }


def test_runtime_readiness_bloqueia_quando_existe_item_critico():
    snapshot = _snapshot(blocked_items=1)

    assert _runtime_ready(snapshot) is False
    assert _runtime_readiness_reason(snapshot) == 'blocked_items_detected'


def test_runtime_readiness_attention_exige_atencao():
    snapshot = _snapshot(status='attention')

    assert _runtime_ready(snapshot) is True
    assert _runtime_readiness_reason(snapshot) == 'runtime_requires_attention'


def test_runtime_readiness_healthy_mantem_estado_saudavel():
    snapshot = _snapshot(status='healthy')

    assert _runtime_readiness_reason(snapshot) == 'runtime_healthy'
