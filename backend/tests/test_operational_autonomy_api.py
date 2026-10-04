from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import operational_autonomy as operational_api
from app.core.operational_queue import OperationalQueue
from app.main import app


def test_operational_task_rejects_divergent_idempotency_intent_with_409(monkeypatch):
    queue = OperationalQueue()
    monkeypatch.setattr(operational_api, 'operational_queue', queue)
    client = TestClient(app)

    headers = {'X-Correlation-Id': 'corr-api-first'}
    first_payload = {
        'task_type': 'generic',
        'payload': {'action': 'first', 'target': 'reqsys'},
        'idempotency_key': 'api-intent-key',
        'max_attempts': 3,
    }
    first = client.post(
        '/api/operational-autonomy/tasks',
        json=first_payload,
        headers=headers,
    )
    assert first.status_code == 202
    task_id = first.json()['data']['task']['task_id']

    replay = client.post(
        '/api/operational-autonomy/tasks',
        json=first_payload,
        headers={'X-Correlation-Id': 'corr-api-replay'},
    )
    assert replay.status_code == 202
    assert replay.json()['data']['task']['task_id'] == task_id

    divergent = {
        **first_payload,
        'payload': {'action': 'different', 'target': 'reqsys'},
    }
    conflict = client.post(
        '/api/operational-autonomy/tasks',
        json=divergent,
        headers={'X-Correlation-Id': 'corr-api-conflict'},
    )
    assert conflict.status_code == 409
    assert conflict.json()['detail'] == (
        'Idempotency-Key já utilizada para outra intenção operacional'
    )

    readback = client.get(f'/api/operational-autonomy/tasks/{task_id}')
    assert readback.status_code == 200
    persisted = readback.json()['data']['task']
    assert persisted['task_id'] == task_id
    assert persisted['idempotency_key'] == 'api-intent-key'
    assert persisted['max_attempts'] == 3
    assert persisted['correlation_id'] == 'corr-api-first'
