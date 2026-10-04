import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_buscar_por_codigo_sem_vinculos():
    resp = client.get("/v1/rastreabilidade/buscar?codigo=REQ-999999999")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["codigo"] == "REQ-999999999"
    assert data["data"]["total"] == 0
    assert data["data"]["vinculos"] == []


def test_buscar_normaliza_codigo_para_maiusculo():
    resp = client.get("/v1/rastreabilidade/buscar?codigo=req-999999999")
    assert resp.status_code == 200
    assert resp.json()["data"]["codigo"] == "REQ-999999999"


def test_recentes_retorna_lista():
    resp = client.get("/v1/rastreabilidade/recentes")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "vinculos" in data["data"]


def test_recentes_filtro_provedor():
    resp = client.get("/v1/rastreabilidade/recentes?provedor=github")
    assert resp.status_code == 200


def test_vinculos_por_requisito_inexistente():
    resp = client.get("/v1/rastreabilidade/requisitos/999999")
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["total"] == 0


def test_adicionar_vinculo_manual_requisito_inexistente():
    resp = client.post(
        "/v1/rastreabilidade/requisitos/999999/vinculos",
        json={
            "tipo": "commit",
            "provedor": "github",
            "repo": "owner/repo",
            "referencia": "abc123",
        },
    )
    assert resp.status_code == 404


def test_webhook_github_ping():
    resp = client.post(
        "/v1/webhooks/github",
        json={"zen": "Keep it logically awesome.", "hook_id": 1},
        headers={"X-GitHub-Event": "ping"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["processado"] is True


def test_webhook_github_push_sem_req():
    payload = {
        "ref": "refs/heads/main",
        "repository": {"full_name": "owner/repo"},
        "commits": [
            {
                "id": "a" * 40,
                "message": "fix: typo no README",
                "author": {"username": "dev1"},
                "url": None,
            }
        ],
    }
    resp = client.post(
        "/v1/webhooks/github",
        json=payload,
        headers={"X-GitHub-Event": "push"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["vinculos_criados"] == 0


def test_webhook_github_push_com_req():
    payload = {
        "ref": "refs/heads/develop",
        "repository": {"full_name": "owner/repo"},
        "commits": [
            {
                "id": "b" * 40,
                "message": "feat: implementa autenticação REQ-123456789",
                "author": {"username": "dev1"},
                "url": "https://github.com/owner/repo/commit/bbb",
            }
        ],
    }
    resp = client.post(
        "/v1/webhooks/github",
        json=payload,
        headers={"X-GitHub-Event": "push"},
    )
    assert resp.status_code == 200
    data = resp.json()
    # REQ-123456789 pode não existir no banco de teste, mas o vínculo é criado
    assert data["data"]["vinculos_criados"] == 1


def test_webhook_gitlab_push_sem_req():
    payload = {
        "ref": "refs/heads/main",
        "project": {"path_with_namespace": "grupo/projeto"},
        "commits": [{"id": "a" * 40, "message": "fix: typo", "author": {}, "url": None}],
    }
    resp = client.post(
        "/v1/webhooks/gitlab",
        json=payload,
        headers={"X-Gitlab-Event": "Push Hook"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["vinculos_criados"] == 0


def test_webhook_evento_nao_suportado():
    resp = client.post(
        "/v1/webhooks/github",
        json={},
        headers={"X-GitHub-Event": "star"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["processado"] is False


def test_matriz_rastreabilidade_endpoint():
    resp = client.get("/v1/rastreabilidade/matriz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "linhas" in body["data"]
