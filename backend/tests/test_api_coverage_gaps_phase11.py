"""Gaps de cobertura — monitoramento operacional e webhooks GitLab (fase 11)."""

from app.api.monitoramento_operacional import (
    _runtime_readiness_reason,
    _runtime_ready,
)
from app.core.config import settings


def test_runtime_ready_false_quando_ha_bloqueios():
    snapshot = {
        'critical_counts': {'blocked_items': 2},
        'evidence': {},
        'status': 'healthy',
    }
    assert _runtime_ready(snapshot) is False


def test_runtime_ready_true_com_deploy_gate_relaxed():
    snapshot = {
        'critical_counts': {'blocked_items': 0},
        'evidence': {'deploy_gate_relaxed': True},
        'status': 'degraded',
    }
    assert _runtime_ready(snapshot) is True


def test_runtime_readiness_reason_bloqueios():
    snapshot = {
        'critical_counts': {'blocked_items': 1},
        'evidence': {},
        'status': 'healthy',
    }
    assert _runtime_readiness_reason(snapshot) == 'blocked_items_detected'


def test_runtime_readiness_reason_deploy_gate_relaxed():
    snapshot = {
        'critical_counts': {'blocked_items': 0},
        'evidence': {'deploy_gate_relaxed': True},
        'status': 'degraded',
    }
    assert _runtime_readiness_reason(snapshot) == 'runtime_healthy'


def test_runtime_readiness_reason_degraded():
    snapshot = {
        'critical_counts': {'blocked_items': 0},
        'evidence': {},
        'status': 'degraded',
    }
    assert _runtime_readiness_reason(snapshot) == 'runtime_degraded'


def test_runtime_readiness_reason_attention():
    snapshot = {
        'critical_counts': {'blocked_items': 0},
        'evidence': {},
        'status': 'attention',
    }
    assert _runtime_readiness_reason(snapshot) == 'runtime_requires_attention'


def test_webhook_gitlab_payload_invalido(client, monkeypatch):
    monkeypatch.setattr(settings, 'gitlab_webhook_token', '')

    response = client.post(
        '/v1/webhooks/gitlab',
        content=b'{json-invalido',
        headers={'X-Gitlab-Event': 'Push Hook', 'Content-Type': 'application/json'},
    )

    assert response.status_code == 400


def test_webhook_gitlab_evento_nao_suportado(client, monkeypatch):
    monkeypatch.setattr(settings, 'gitlab_webhook_token', '')

    response = client.post(
        '/v1/webhooks/gitlab',
        json={'object_kind': 'pipeline'},
        headers={'X-Gitlab-Event': 'Pipeline Hook'},
    )

    assert response.status_code == 200
    data = response.json()['data']
    assert data['processado'] is False
    assert 'não suportado' in data['motivo'].lower()
