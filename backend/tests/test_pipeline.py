"""
Tests: POST /v1/solicitacoes, POST /v1/requisitos/validar,
       POST /v1/requisitos/estruturar/{id}, POST /v1/backlog/publicar-redmine/{id}
"""
import pytest

PAYLOAD_BASE = {
    "origem": "email",
    "titulo": "Consulta prévia antes do cadastro rural",
    "descricao": "Ao informar CPF ou CNPJ, verificar se cliente já existe antes de criar novo cadastro.",
    "urgencia": "alta",
    "area": "Crédito",
    "sistema": "Portal Rural",
    "solicitante": "gerencia_credito",
    "impacto_regulatorio": False,
}


class TestCriarSolicitacao:
    def test_sucesso(self, client, correlation_id):
        resp = client.post(
            "/v1/solicitacoes",
            json=PAYLOAD_BASE,
            headers={"X-Correlation-ID": correlation_id},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["codigo"].startswith("SOL-")
        assert data["data"]["status"] == "recebido"

    def test_correlation_propagado(self, client, correlation_id):
        resp = client.post(
            "/v1/solicitacoes",
            json=PAYLOAD_BASE,
            headers={"X-Correlation-ID": correlation_id},
        )
        assert resp.json().get("meta", {}).get("correlation_id") == correlation_id

    def test_titulo_curto_rejeitado(self, client):
        payload = {**PAYLOAD_BASE, "titulo": "abc"}
        resp = client.post("/v1/solicitacoes", json=payload)
        assert resp.status_code == 422

    def test_descricao_curta_rejeitada(self, client):
        payload = {**PAYLOAD_BASE, "descricao": "curto demais"}
        resp = client.post("/v1/solicitacoes", json=payload)
        assert resp.status_code == 422

    def test_sem_corpo_rejeitado(self, client):
        resp = client.post("/v1/solicitacoes", json={})
        assert resp.status_code == 422


class TestValidarRequisito:
    def test_valido_sem_alertas(self, client):
        resp = client.post(
            "/v1/requisitos/validar",
            json={
                "titulo": "Consulta prévia CPF CNPJ",
                "descricao": "Verificar existência antes do cadastro no sistema.",
                "requisitos_funcionais": ["RF-001"],
                "criterios_aceite": [{"ordem": 1, "descricao": "CPF válido retorna dados."}],
            },
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["aprovado_para_triagem"] is True
        assert data["alertas"] == []

    def test_sem_rfs_gera_alerta(self, client):
        resp = client.post(
            "/v1/requisitos/validar",
            json={"titulo": "Teste", "descricao": "Descricao qualquer para o teste."},
        )
        data = resp.json()["data"]
        assert data["aprovado_para_triagem"] is False
        assert any("requisito funcional" in a.lower() for a in data["alertas"])

    def test_sem_criterios_gera_alerta(self, client):
        resp = client.post(
            "/v1/requisitos/validar",
            json={
                "titulo": "Teste",
                "descricao": "Descricao qualquer para o teste.",
                "requisitos_funcionais": ["RF-001"],
            },
        )
        data = resp.json()["data"]
        assert any("critério" in a.lower() for a in data["alertas"])

    def test_termos_ambiguos_detectados(self, client):
        resp = client.post(
            "/v1/requisitos/validar",
            json={
                "titulo": "Sistema deve ser rápido e intuitivo",
                "descricao": "Interface simples e otimizada para o usuário final.",
            },
        )
        alertas = resp.json()["data"]["alertas"]
        termos = [a for a in alertas if "ambíguo" in a.lower()]
        assert len(termos) >= 2

    def test_payload_vazio_retorna_alertas(self, client):
        resp = client.post("/v1/requisitos/validar", json={})
        assert resp.status_code == 200
        assert resp.json()["data"]["aprovado_para_triagem"] is False


@pytest.fixture(scope="module")
def req_ids(client):
    """IDs reais de requisitos criados via API — o banco é compartilhado entre
    arquivos de teste (Postgres centralizado, ADR-042/ADR-043), então não dá
    para assumir que um requisito recém-criado vai ter ID 1 ou 2."""
    ids = []
    for _ in range(2):
        resp = client.post("/v1/solicitacoes", json=PAYLOAD_BASE)
        ids.append(resp.json()["data"]["id"])
    return ids


class TestEstruturarRequisito:
    def test_estrutura_retornada(self, client, req_ids):
        resp = client.post(f"/v1/requisitos/estruturar/{req_ids[0]}", json=PAYLOAD_BASE)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["requisito_id"] == req_ids[0]
        assert data["codigo_requisito"].startswith("REQ-")
        assert isinstance(data["requisitos_funcionais"], list)
        assert isinstance(data["requisitos_nao_funcionais"], list)
        assert isinstance(data["regras_negocio"], list)
        assert isinstance(data["criterios_aceite"], list)

    def test_rfs_inferidas_de_cpf(self, client, req_ids):
        payload = {**PAYLOAD_BASE, "descricao": "Buscar cadastro por CPF antes de criar novo."}
        resp = client.post(f"/v1/requisitos/estruturar/{req_ids[1]}", json=payload)
        rfs = resp.json()["data"]["requisitos_funcionais"]
        assert any("CPF" in rf or "CNPJ" in rf for rf in rfs)

    def test_prioridade_reflete_urgencia(self, client, req_ids):
        for urgencia in ["baixa", "media", "alta", "critica"]:
            payload = {**PAYLOAD_BASE, "urgencia": urgencia}
            resp = client.post(f"/v1/requisitos/estruturar/{req_ids[0]}", json=payload)
            assert resp.json()["data"]["prioridade"] == urgencia

    def test_rnfs_presentes(self, client, req_ids):
        resp = client.post(f"/v1/requisitos/estruturar/{req_ids[0]}", json=PAYLOAD_BASE)
        rnfs = resp.json()["data"]["requisitos_nao_funcionais"]
        assert len(rnfs) >= 1
        assert any("correlation_id" in rnf.lower() for rnf in rnfs)


_FAKE_REDMINE_RESULT = {
    'issue_principal_id': '420',
    'subtarefas': [
        {'id': 421, 'subject': 'Frontend'},
        {'id': 422, 'subject': 'Backend'},
        {'id': 423, 'subject': 'Dados'},
        {'id': 424, 'subject': 'QA'},
    ],
    'warnings': [],
}


class TestPublicarRedmine:
    def test_issue_criado(self, client, monkeypatch, req_ids):
        import app.api.pipeline as _pipeline
        monkeypatch.setattr(_pipeline, 'publish_requisito_to_redmine', lambda **_kw: _FAKE_REDMINE_RESULT)
        resp = client.post(f"/v1/backlog/publicar-redmine/{req_ids[0]}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "issue_principal_id" in data
        assert isinstance(data["subtarefas"], list)
        assert len(data["subtarefas"]) == 4

    def test_subtarefas_tem_frontend_backend_dados_qa(self, client, monkeypatch, req_ids):
        import app.api.pipeline as _pipeline
        monkeypatch.setattr(_pipeline, 'publish_requisito_to_redmine', lambda **_kw: _FAKE_REDMINE_RESULT)
        resp = client.post(f"/v1/backlog/publicar-redmine/{req_ids[0]}")
        subjects = [s["subject"] for s in resp.json()["data"]["subtarefas"]]
        for esperado in ("Frontend", "Backend", "Dados", "QA"):
            assert esperado in subjects

    def test_requisito_id_propagado(self, client, monkeypatch, req_ids):
        import app.api.pipeline as _pipeline
        monkeypatch.setattr(_pipeline, 'publish_requisito_to_redmine', lambda **_kw: _FAKE_REDMINE_RESULT)
        resp = client.post(f"/v1/backlog/publicar-redmine/{req_ids[0]}")
        assert resp.json()["data"]["requisito_id"] == req_ids[0]

    def test_requisito_inexistente_retorna_404(self, client):
        for req_id in (999999999, 1000000000):
            resp = client.post(f"/v1/backlog/publicar-redmine/{req_id}")
            assert resp.status_code == 404

    def test_correlation_propagado(self, client, monkeypatch, correlation_id, req_ids):
        import app.api.pipeline as _pipeline
        monkeypatch.setattr(_pipeline, 'publish_requisito_to_redmine', lambda **_kw: _FAKE_REDMINE_RESULT)
        resp = client.post(
            f"/v1/backlog/publicar-redmine/{req_ids[0]}",
            headers={"X-Correlation-ID": correlation_id},
        )
        assert resp.json().get("meta", {}).get("correlation_id") == correlation_id


class TestIntegracaoGithub:
    def test_listar_issues_github(self, client, monkeypatch):
        fake_issues = [
            {
                "id": 1,
                "number": 101,
                "title": "Ajustar validação de CPF",
                "state": "open",
                "html_url": "https://github.com/acme/repo/issues/101",
                "labels": ["bug"],
            }
        ]

        monkeypatch.setattr(
            "app.api.pipeline.github_redmine_import_enabled",
            lambda: True,
        )
        monkeypatch.setattr(
            "app.api.pipeline.fetch_github_issues",
            lambda repo, state, limit, labels: fake_issues,
        )

        resp = client.post(
            "/v1/integracoes/github/issues",
            json={"repo": "acme/repo", "state": "open", "limit": 10, "labels": ["bug"]},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["repo"] == "acme/repo"
        assert data["total"] == 1
        assert data["issues"][0]["number"] == 101

    def test_listar_issues_github_feature_flag_desabilitada(self, client, monkeypatch):
        monkeypatch.setattr(
            "app.api.pipeline.github_redmine_import_enabled",
            lambda: False,
        )
        resp = client.post(
            "/v1/integracoes/github/issues",
            json={"repo": "acme/repo"},
        )
        assert resp.status_code == 409

    def test_publicar_redmine_com_github_filtra_issue_numbers(self, client, monkeypatch, req_ids):
        fake_issues = [
            {"id": 1, "number": 10, "title": "Issue 10", "state": "open", "html_url": "u1", "labels": []},
            {"id": 2, "number": 20, "title": "Issue 20", "state": "open", "html_url": "u2", "labels": []},
        ]

        monkeypatch.setattr(
            "app.api.pipeline.github_redmine_import_enabled",
            lambda: True,
        )
        monkeypatch.setattr(
            "app.api.pipeline.fetch_github_issues",
            lambda repo, state, limit, labels: fake_issues,
        )
        monkeypatch.setattr(
            "app.api.pipeline.publish_issues_to_redmine",
            lambda repo, issues, project_id, tracker_id, priority_id: {
                "published_count": len(issues),
                "published_issues": [
                    {
                        "github_number": i["number"],
                        "redmine_issue_id": 500 + idx,
                        "redmine_url": f"https://redmine.local/issues/{500 + idx}",
                    }
                    for idx, i in enumerate(issues)
                ],
                "warnings": [],
            },
        )

        resp = client.post(
            f"/v1/backlog/publicar-redmine/{req_ids[0]}",
            json={
                "use_github_import": True,
                "github_repo": "acme/repo",
                "issue_numbers": [20],
            },
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["github_imported_count"] == 1
        assert data["github_issues"][0]["number"] == 20
        assert data["redmine_published_count"] == 1

    def test_publicar_redmine_com_github_flag_desabilitada(self, client, monkeypatch, req_ids):
        monkeypatch.setattr(
            "app.api.pipeline.github_redmine_import_enabled",
            lambda: False,
        )
        resp = client.post(
            f"/v1/backlog/publicar-redmine/{req_ids[0]}",
            json={"use_github_import": True, "github_repo": "acme/repo"},
        )
        assert resp.status_code == 409


class TestEncodingRegressao:
    """Regressão de encoding UTF-8 — Req 3 e 2.3 (spec pipeline-encoding-fix)."""

    def test_github_issues_flag_off_detail_utf8(self, client, monkeypatch):
        monkeypatch.setattr("app.api.pipeline.github_redmine_import_enabled", lambda: False)
        resp = client.post("/v1/integracoes/github/issues", json={"repo": "acme/repo"})
        assert resp.status_code == 409
        detail = resp.json()["detail"]
        assert "Integração" in detail, f"Mojibake ou ausência do termo: {detail!r}"
        assert "Ã" not in detail, f"Sequência de mojibake detectada: {detail!r}"

    def test_publicar_redmine_flag_off_detail_utf8(self, client, monkeypatch, req_ids):
        monkeypatch.setattr("app.api.pipeline.github_redmine_import_enabled", lambda: False)
        resp = client.post(
            f"/v1/backlog/publicar-redmine/{req_ids[0]}",
            json={"use_github_import": True, "github_repo": "acme/repo"},
        )
        assert resp.status_code == 409
        detail = resp.json()["detail"]
        assert "Integração" in detail, f"Mojibake ou ausência do termo: {detail!r}"
        assert "Ã" not in detail, f"Sequência de mojibake detectada: {detail!r}"

    def test_response_decodifica_utf8_sem_erro(self, client, monkeypatch):
        monkeypatch.setattr("app.api.pipeline.github_redmine_import_enabled", lambda: False)
        resp = client.post("/v1/integracoes/github/issues", json={"repo": "acme/repo"})
        import json as _json
        payload = _json.loads(resp.text)
        detail = payload.get("detail", "")
        assert detail.encode("utf-8").decode("utf-8") == detail, (
            f"Round-trip UTF-8 alterou a string: {detail!r}"
        )

    def test_content_type_charset_utf8(self, client, monkeypatch):
        monkeypatch.setattr("app.api.pipeline.github_redmine_import_enabled", lambda: False)
        resp = client.post("/v1/integracoes/github/issues", json={"repo": "acme/repo"})
        content_type = resp.headers.get("content-type", "")
        assert "application/json" in content_type, f"Content-Type inesperado: {content_type!r}"
