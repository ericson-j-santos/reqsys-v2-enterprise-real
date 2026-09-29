from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.change_evidence import ChangeEvidenceRecord
from app.core.security import get_current_user
from app.services.change_impact_analysis import (
    analyze_live_change,
    artifacts_from_traceability_graph,
)
from app.db import Base, get_db
from app.main import app
from app.models.agile_runtime import AgileWorkItem
from app.models.requisito import Requisito
from app.models.vinculo_git import VinculoGit

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
client = TestClient(app)


def _user_override():
    return {"sub": "traceability-test", "papel": "admin"}


def _db_override():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _isolated_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = _db_override
    app.dependency_overrides[get_current_user] = _user_override
    yield
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


def _seed_graph(*, runtime_sha: str | None = None, status: str = "PASSED") -> tuple[int, str]:
    head_sha = "a" * 40
    db = TestingSession()
    try:
        requisito = Requisito(
            codigo="REQ-TRACE-0001",
            titulo="Rastreabilidade ponta a ponta",
            descricao="Requisito usado para validar a projeção read-only de rastreabilidade.",
            urgencia="alta",
            area="Engenharia",
            sistema="ReqSys",
            solicitante="teste",
            status="aprovado",
            impacto_regulatorio=False,
        )
        db.add(requisito)
        db.flush()

        db.add(
            AgileWorkItem(
                codigo="WI-TRACE-0001",
                tipo="historia",
                titulo="Implementar projeção de rastreabilidade",
                descricao="Work item ligado ao requisito para validar a projeção.",
                status="em_andamento",
                prioridade="P1",
                requisito_id=requisito.id,
                repositorio="ericson-j-santos/reqsys-v2-enterprise-real",
                branch="feat/traceability-graph-projection-20260929",
                change_provider="github",
                change_id="2161",
                change_url="https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/pull/2161",
                ci_provider="github_actions",
                ci_run_id="36520000001",
                ci_status="success",
                ambiente_deploy="dev",
                deploy_status="success",
            )
        )
        db.add(
            VinculoGit(
                requisito_codigo=requisito.codigo,
                requisito_id=requisito.id,
                tipo="pr",
                provedor="github",
                repo="ericson-j-santos/reqsys-v2-enterprise-real",
                referencia="2161",
                url="https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/pull/2161",
                titulo="Traceability Graph",
                autor="reqsys-test",
                ambiente="dev",
            )
        )
        db.add(
            VinculoGit(
                requisito_codigo=requisito.codigo,
                requisito_id=requisito.id,
                tipo="commit",
                provedor="github",
                repo="ericson-j-santos/reqsys-v2-enterprise-real",
                referencia=head_sha,
                url=f"https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/commit/{head_sha}",
                titulo="Traceability Graph",
                autor="reqsys-test",
                ambiente="dev",
            )
        )

        event_id = str(uuid4())
        db.add(
            ChangeEvidenceRecord(
                event_id=event_id,
                case_id=str(uuid4()),
                requirement_ref=requisito.codigo,
                sdd_ref=".sdd/specs/traceability-graph-projection.requirements.md",
                pull_request_ref="PR-2161",
                head_sha=head_sha,
                ci_run_id="36520000001",
                ci_conclusion="success",
                deployment_ref="github-actions:traceability-dev",
                environment="dev",
                runtime_sha=runtime_sha or head_sha,
                post_deploy_evidence_uri="urn:reqsys:traceability-graph:e2e",
                post_deploy_evidence_sha256="b" * 64,
                status=status,
                observed_at=datetime(2026, 9, 29, 20, 0, tzinfo=timezone.utc),
                correlation_id="traceability-graph-e2e",
                payload_sha256="c" * 64,
            )
        )
        db.commit()
        return requisito.id, event_id
    finally:
        db.close()


def test_traceability_graph_e2e_projects_requirement_to_runtime_and_replay_is_stable():
    requisito_id, event_id = _seed_graph()

    db = TestingSession()
    try:
        before = db.query(ChangeEvidenceRecord).count()
    finally:
        db.close()

    first = client.get(f"/v1/rastreabilidade/requisitos/{requisito_id}/grafo")
    second = client.get(f"/v1/rastreabilidade/requisitos/{requisito_id}/grafo")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["data"] == second.json()["data"]

    graph = first.json()["data"]
    assert graph["graph_type"] == "functional_traceability_graph"
    assert graph["schema_version"] == "1.1.0"
    assert graph["requirement"]["code"] == "REQ-TRACE-0001"
    assert "REQUIREMENT" in {node["type"] for node in graph["nodes"]}
    assert graph["summary"]["valid_evidence_count"] == 1
    assert graph["summary"]["rejected_evidence_count"] == 0

    relations = {
        (edge["relation"], edge["evidence_status"])
        for edge in graph["edges"]
    }
    assert ("specified_by", "reference") in relations
    assert ("implemented_by", "reference") in relations
    assert ("verified_by", "verified") in relations
    assert ("deployed_as", "verified") in relations
    assert ("observed_as", "verified") in relations

    runtime_node = next(
        node
        for node in graph["nodes"]
        if node["id"] == f"runtime_evidence:{event_id}"
    )
    assert runtime_node["metadata"]["head_sha"] == "a" * 40
    assert runtime_node["metadata"]["runtime_sha"] == "a" * 40

    db = TestingSession()
    try:
        after = db.query(ChangeEvidenceRecord).count()
        assert after == before == 1
    finally:
        db.close()


def test_traceability_graph_rejects_runtime_sha_mismatch_as_valid_evidence():
    requisito_id, event_id = _seed_graph(runtime_sha="d" * 40)

    response = client.get(f"/v1/rastreabilidade/requisitos/{requisito_id}/grafo")

    assert response.status_code == 200
    graph = response.json()["data"]
    assert graph["summary"]["valid_evidence_count"] == 0
    assert graph["summary"]["rejected_evidence_count"] == 1
    assert graph["rejected_evidence"] == [
        {
            "event_id": event_id,
            "head_sha": "a" * 40,
            "runtime_sha": "d" * 40,
            "reasons": ["runtime_sha_mismatch"],
        }
    ]

    evidence_edges = [
        edge
        for edge in graph["edges"]
        if edge["relation"] in {"verified_by", "deployed_as", "observed_as"}
    ]
    assert evidence_edges
    assert all(edge["evidence_status"] == "rejected" for edge in evidence_edges)
    assert all("runtime_sha_mismatch" in edge["reasons"] for edge in evidence_edges)


def test_traceability_graph_failed_runtime_is_not_valid_evidence():
    requisito_id, _ = _seed_graph(status="FAILED")

    response = client.get(f"/v1/rastreabilidade/requisitos/{requisito_id}/grafo")

    assert response.status_code == 200
    graph = response.json()["data"]
    assert graph["summary"]["valid_evidence_count"] == 0
    assert graph["summary"]["rejected_evidence_count"] == 1
    assert graph["rejected_evidence"][0]["reasons"] == [
        "runtime_status_not_satisfactory"
    ]


def test_traceability_graph_requirement_not_found():
    response = client.get("/v1/rastreabilidade/requisitos/999999/grafo")

    assert response.status_code == 404
    assert response.json()["detail"] == "Requisito não encontrado."


def test_traceability_graph_requires_authenticated_user():
    requisito_id, _ = _seed_graph()
    app.dependency_overrides.pop(get_current_user, None)
    try:
        response = client.get(f"/v1/rastreabilidade/requisitos/{requisito_id}/grafo")
    finally:
        app.dependency_overrides[get_current_user] = _user_override

    assert response.status_code == 401
    assert response.json()["detail"] == "Token não fornecido"



def test_traceability_graph_feeds_live_change_impact_without_historical_dataset():
    requisito_id, _ = _seed_graph()

    response = client.get(f"/v1/rastreabilidade/requisitos/{requisito_id}/grafo")

    assert response.status_code == 200
    graph = response.json()["data"]
    results = analyze_live_change(
        graph,
        change_id="CHANGE-LIVE-TRACE-1",
        query="avaliar impacto da mudança na rastreabilidade e evidência runtime",
        llm_generate=None,
        correlation_id="live-traceability-impact-e2e",
    )

    by_strategy = {result.strategy: result for result in results}
    assert set(by_strategy) == {"graph", "semantic", "hybrid_rag_llm"}
    assert by_strategy["graph"].candidates
    assert by_strategy["hybrid_rag_llm"].llm_status == "disabled"

    graph_node_ids = {node["id"] for node in graph["nodes"]}
    for result in results:
        assert all(
            candidate.artifact_id in graph_node_ids
            for candidate in result.candidates
        )
        assert all(candidate.evidence for candidate in result.candidates)


def test_live_change_impact_excludes_rejected_runtime_and_filters_llm_hallucination():
    requisito_id, event_id = _seed_graph(runtime_sha="d" * 40)

    response = client.get(f"/v1/rastreabilidade/requisitos/{requisito_id}/grafo")

    assert response.status_code == 200
    graph = response.json()["data"]
    artifacts = artifacts_from_traceability_graph(graph)
    artifact_ids = {artifact.artifact_id for artifact in artifacts}

    assert f"runtime_evidence:{event_id}" not in artifact_ids
    assert "ci_run:36520000001" not in artifact_ids
    assert "deployment:github-actions:traceability-dev" not in artifact_ids

    valid_candidate = (
        "git:github:ericson-j-santos/reqsys-v2-enterprise-real:pr:2161"
    )
    assert valid_candidate in artifact_ids

    def fake_llm(prompt: str, correlation_id: str) -> str:
        assert correlation_id == "live-impact-negative-control"
        assert f"runtime_evidence:{event_id}" not in prompt
        return (
            '{"candidates":['
            '{"artifact_id":"'
            + valid_candidate
            + '","relation":"TRACEABLE_CHANGE","confidence":0.94,'
            '"reason":"candidato presente no grafo vivo"},'
            '{"artifact_id":"UNKNOWN-HALLUCINATION","relation":"MADE_UP",'
            '"confidence":1.0,"reason":"não existe"}'
            ']}'
        )

    results = analyze_live_change(
        graph,
        change_id="CHANGE-LIVE-TRACE-NEGATIVE",
        query="avaliar impacto sem aceitar evidência runtime rejeitada",
        llm_generate=fake_llm,
        correlation_id="live-impact-negative-control",
    )
    hybrid = next(result for result in results if result.strategy == "hybrid_rag_llm")

    assert hybrid.llm_status == "used"
    assert [candidate.artifact_id for candidate in hybrid.candidates] == [
        valid_candidate
    ]



def test_live_impact_operational_api_e2e_is_read_only_and_replay_stable():
    requisito_id, _ = _seed_graph()
    payload = {
        "change_id": "CHANGE-OPERATIONAL-TRACE-1",
        "query": "avaliar impacto operacional da mudança usando rastreabilidade viva",
        "llm_enabled": False,
    }
    headers = {"X-Correlation-Id": "live-impact-operational-e2e"}

    db = TestingSession()
    try:
        before_evidence = db.query(ChangeEvidenceRecord).count()
        before_links = db.query(VinculoGit).count()
        before_items = db.query(AgileWorkItem).count()
    finally:
        db.close()

    graph_response = client.get(
        f"/v1/rastreabilidade/requisitos/{requisito_id}/grafo",
        headers=headers,
    )
    first = client.post(
        f"/v1/rastreabilidade/requisitos/{requisito_id}/impacto",
        json=payload,
        headers=headers,
    )
    second = client.post(
        f"/v1/rastreabilidade/requisitos/{requisito_id}/impacto",
        json=payload,
        headers=headers,
    )

    assert graph_response.status_code == 200
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["data"] == second.json()["data"]
    assert first.json()["meta"]["correlation_id"] == "live-impact-operational-e2e"

    data = first.json()["data"]
    assert data["change_id"] == payload["change_id"]
    assert data["source"] == "live_traceability_graph"
    assert data["historical_dataset_used"] is False
    assert data["read_only"] is True
    assert data["requirement"]["code"] == "REQ-TRACE-0001"

    strategies = {item["strategy"]: item for item in data["strategies"]}
    assert set(strategies) == {"graph", "semantic", "hybrid_rag_llm"}
    assert strategies["graph"]["candidates"]
    assert strategies["hybrid_rag_llm"]["llm_status"] == "disabled"

    graph_node_ids = {
        node["id"]
        for node in graph_response.json()["data"]["nodes"]
    }
    for strategy in strategies.values():
        assert all(
            candidate["artifact_id"] in graph_node_ids
            for candidate in strategy["candidates"]
        )
        assert all(
            candidate["evidence"]
            for candidate in strategy["candidates"]
        )

    db = TestingSession()
    try:
        assert db.query(ChangeEvidenceRecord).count() == before_evidence == 1
        assert db.query(VinculoGit).count() == before_links == 2
        assert db.query(AgileWorkItem).count() == before_items == 1
    finally:
        db.close()


def test_live_impact_operational_api_excludes_rejected_runtime_evidence():
    requisito_id, event_id = _seed_graph(runtime_sha="d" * 40)

    response = client.post(
        f"/v1/rastreabilidade/requisitos/{requisito_id}/impacto",
        json={
            "change_id": "CHANGE-OPERATIONAL-NEGATIVE",
            "query": "avaliar impacto sem promover evidência runtime rejeitada",
        },
        headers={"X-Correlation-Id": "live-impact-operational-negative"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    candidate_ids = {
        candidate["artifact_id"]
        for strategy in data["strategies"]
        for candidate in strategy["candidates"]
    }

    assert f"runtime_evidence:{event_id}" not in candidate_ids
    assert "ci_run:36520000001" not in candidate_ids
    assert "deployment:github-actions:traceability-dev" not in candidate_ids
    assert data["graph_summary"]["rejected_evidence_count"] == 1


def test_live_impact_operational_api_rejects_unknown_seed():
    requisito_id, _ = _seed_graph()

    response = client.post(
        f"/v1/rastreabilidade/requisitos/{requisito_id}/impacto",
        json={
            "change_id": "CHANGE-OPERATIONAL-BAD-SEED",
            "query": "avaliar impacto",
            "seed_artifact_ids": ["unknown:seed"],
        },
    )

    assert response.status_code == 422
    assert "seeds ausentes da rastreabilidade viva" in response.json()["detail"]


def test_live_impact_operational_api_requirement_not_found():
    response = client.post(
        "/v1/rastreabilidade/requisitos/999999/impacto",
        json={
            "change_id": "CHANGE-OPERATIONAL-NOT-FOUND",
            "query": "avaliar impacto",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Requisito não encontrado."


def test_live_impact_operational_api_requires_authenticated_user():
    requisito_id, _ = _seed_graph()
    app.dependency_overrides.pop(get_current_user, None)
    try:
        response = client.post(
            f"/v1/rastreabilidade/requisitos/{requisito_id}/impacto",
            json={
                "change_id": "CHANGE-OPERATIONAL-AUTH",
                "query": "avaliar impacto",
            },
        )
    finally:
        app.dependency_overrides[get_current_user] = _user_override

    assert response.status_code == 401
    assert response.json()["detail"] == "Token não fornecido"
