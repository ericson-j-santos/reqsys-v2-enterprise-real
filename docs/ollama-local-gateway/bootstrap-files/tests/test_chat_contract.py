from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from reqsys_ollama_gateway.app import app


def test_chat_contract_mock_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('REQSYS_AUTH_REQUIRED', 'false')
    client = TestClient(app)
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {'response': 'analise via ollama local'}

    with patch('reqsys_ollama_gateway.ollama_client.httpx.Client') as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client

        resposta = client.post(
            '/v1/chat',
            json={
                'model': 'qwen2.5-coder:7b',
                'task_type': 'code',
                'prompt': 'analisar codigo',
                'contexto': 'reqsys',
                'entrada': 'def foo(): pass',
                'correlation_id': 'corr-chat-001',
                'source': 'reqsys-codex',
            },
            headers={'X-Correlation-Id': 'corr-chat-001'},
        )

    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados['response'] == 'analise via ollama local'
    assert dados['correlation_id'] == 'corr-chat-001'
    assert dados['model'] == 'qwen2.5-coder:7b'
