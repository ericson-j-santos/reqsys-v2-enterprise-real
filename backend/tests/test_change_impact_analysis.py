import json
from pathlib import Path

import pytest

from app.services.change_impact_analysis import (
    ChangeImpactValidationError,
    HistoricalChange,
    ImpactArtifact,
    LiveChange,
    analyze_live_change,
    artifacts_from_traceability_graph,
    graph_candidates,
    hybrid_candidates,
    load_dataset,
    semantic_candidates,
)

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "data" / "change-impact" / "historical-ground-truth-v1.json"


@pytest.fixture()
def dataset():
    payload = json.loads(DATASET.read_text(encoding="utf-8"))
    return load_dataset(payload)


def test_graph_strategy_recovers_known_rsm07_impact(dataset):
    artifacts, changes = dataset
    change = next(
        item
        for item in changes
        if item.change_id == "RSM-07-RUNTIME-SHA-ROLLBACK"
    )

    result = graph_candidates(change, artifacts)

    ids = {item.artifact_id for item in result.candidates}
    assert ids == set(change.ground_truth)
    assert all(item.evidence for item in result.candidates)
    assert all(item.strategy == "graph" for item in result.candidates)


def test_semantic_strategy_uses_existing_local_rag_and_excludes_seed(dataset):
    artifacts, changes = dataset
    change = next(item for item in changes if item.change_id == "RSM-08-ROOT-CAUSE")

    result = semantic_candidates(change, artifacts, top_k=6)

    ids = {item.artifact_id for item in result.candidates}
    assert ids
    assert not ids.intersection(change.seed_artifact_ids)
    assert any(item.artifact_id in change.ground_truth for item in result.candidates)
    assert all(item.relation == "SEMANTIC_SIMILARITY" for item in result.candidates)


def test_hybrid_llm_can_only_select_retrieved_artifacts(dataset):
    artifacts, changes = dataset
    change = next(
        item
        for item in changes
        if item.change_id == "RSM-07-RUNTIME-SHA-ROLLBACK"
    )

    def fake_llm(prompt: str, correlation_id: str) -> str:
        assert correlation_id == "impact-test"
        assert "UNKNOWN-HALLUCINATION" not in prompt
        return json.dumps(
            {
                "candidates": [
                    {
                        "artifact_id": "TEST-CHANGE-EVIDENCE",
                        "relation": "VALIDATES_CHANGE_RUNTIME",
                        "confidence": 0.91,
                        "reason": "Cobre runtime SHA, rollback e replay.",
                    },
                    {
                        "artifact_id": "UNKNOWN-HALLUCINATION",
                        "relation": "MADE_UP",
                        "confidence": 1.0,
                        "reason": "não existe",
                    },
                ]
            }
        )

    result = hybrid_candidates(
        change,
        artifacts,
        llm_generate=fake_llm,
        correlation_id="impact-test",
    )

    assert result.llm_status == "used"
    assert [item.artifact_id for item in result.candidates] == [
        "TEST-CHANGE-EVIDENCE"
    ]
    candidate = result.candidates[0]
    assert candidate.strategy == "hybrid_rag_llm"
    assert "backend/tests/test_change_evidence_api.py" in candidate.evidence


def test_hybrid_invalid_llm_output_fails_closed_without_candidates(dataset):
    artifacts, changes = dataset
    change = changes[0]

    result = hybrid_candidates(
        change,
        artifacts,
        llm_generate=lambda _prompt, _correlation_id: "not-json",
    )

    assert result.llm_status == "invalid_or_unavailable"
    assert result.candidates == ()


def test_hybrid_disabled_is_explicit_retrieval_fallback(dataset):
    artifacts, changes = dataset

    result = hybrid_candidates(changes[0], artifacts, llm_generate=None)

    assert result.llm_status == "disabled"
    assert result.candidates
    assert all(
        item.strategy == "hybrid_retrieval_fallback"
        for item in result.candidates
    )


def test_dataset_rejects_unknown_ground_truth():
    artifacts = (
        ImpactArtifact(
            artifact_id="REQ-1",
            kind="REQUIREMENT",
            text="texto",
            source_uri="requirements.md",
        ),
    )
    changes = (
        HistoricalChange(
            change_id="CHANGE-1",
            query="mudança",
            seed_artifact_ids=("REQ-1",),
            ground_truth=frozenset({"MISSING"}),
        ),
    )

    from app.services.change_impact_analysis import validate_dataset

    with pytest.raises(ChangeImpactValidationError, match="artefatos inexistentes"):
        validate_dataset(artifacts, changes)



def _live_traceability_graph_payload():
    return {
        "graph_type": "functional_traceability_graph",
        "schema_version": "1.1.0",
        "requirement": {"id": 7, "code": "REQ-LIVE-7", "status": "aprovado"},
        "nodes": [
            {
                "id": "requirement:REQ-LIVE-7",
                "type": "REQUIREMENT",
                "label": "REQ-LIVE-7",
                "source_uri": None,
                "metadata": None,
            },
            {
                "id": "runtime_evidence:rejected-1",
                "type": "RUNTIME_EVIDENCE",
                "label": "rejected-1",
                "source_uri": "urn:reqsys:runtime:rejected-1",
                "metadata": {"status": "FAILED"},
            },
        ],
        "edges": [
            {
                "source": "requirement:REQ-LIVE-7",
                "target": "runtime_evidence:rejected-1",
                "relation": "observed_as",
                "evidence_status": "rejected",
                "reasons": ["runtime_status_not_satisfactory"],
            }
        ],
        "rejected_evidence": [],
        "summary": {
            "node_count": 2,
            "edge_count": 1,
            "valid_evidence_count": 0,
            "rejected_evidence_count": 1,
        },
    }


def test_live_graph_adapter_excludes_rejected_by_default_and_allows_diagnostic_opt_in():
    graph = _live_traceability_graph_payload()

    operational = artifacts_from_traceability_graph(graph)
    diagnostic = artifacts_from_traceability_graph(
        graph,
        include_rejected_evidence=True,
    )

    assert [item.artifact_id for item in operational] == [
        "requirement:REQ-LIVE-7"
    ]
    assert operational[0].source_uri == "/v1/rastreabilidade/requisitos/7/grafo"
    assert '"metadata": {}' in operational[0].text

    diagnostic_map = {item.artifact_id: item for item in diagnostic}
    assert set(diagnostic_map) == {
        "requirement:REQ-LIVE-7",
        "runtime_evidence:rejected-1",
    }
    assert diagnostic_map["requirement:REQ-LIVE-7"].links == (
        "runtime_evidence:rejected-1",
    )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {"graph_type": "other", "nodes": [], "edges": []},
            "graph_type incompatível",
        ),
        (
            {
                "graph_type": "functional_traceability_graph",
                "requirement": {"id": 1, "code": "REQ-1"},
                "nodes": {},
                "edges": [],
            },
            r"nodes\[\] e edges\[\]",
        ),
        (
            {
                "graph_type": "functional_traceability_graph",
                "requirement": {"id": 1, "code": "REQ-1"},
                "nodes": ["invalid"],
                "edges": [],
            },
            "node inválido",
        ),
        (
            {
                "graph_type": "functional_traceability_graph",
                "requirement": {"id": 1, "code": "REQ-1"},
                "nodes": [{"id": ""}],
                "edges": [],
            },
            "node sem id",
        ),
        (
            {
                "graph_type": "functional_traceability_graph",
                "requirement": {"id": 1, "code": "REQ-1"},
                "nodes": [{"id": "n"}, {"id": "n"}],
                "edges": [],
            },
            "node id duplicado",
        ),
        (
            {
                "graph_type": "functional_traceability_graph",
                "requirement": {"id": 1, "code": "REQ-1"},
                "nodes": [
                    {"id": "n", "type": "X", "label": "n", "metadata": {}}
                ],
                "edges": ["invalid"],
            },
            "edge inválida",
        ),
        (
            {
                "graph_type": "functional_traceability_graph",
                "requirement": {"id": 1, "code": "REQ-1"},
                "nodes": [
                    {"id": "n", "type": "X", "label": "n", "metadata": {}}
                ],
                "edges": [
                    {
                        "source": "n",
                        "target": "n",
                        "evidence_status": "reference",
                    }
                ],
            },
            "edge sem source, target ou relation",
        ),
        (
            {
                "graph_type": "functional_traceability_graph",
                "requirement": {"id": 1, "code": "REQ-1"},
                "nodes": [
                    {"id": "n", "type": "X", "label": "n", "metadata": {}}
                ],
                "edges": [
                    {
                        "source": "n",
                        "target": "missing",
                        "relation": "related_to",
                        "evidence_status": "reference",
                    }
                ],
            },
            "edge referencia node inexistente",
        ),
        (
            {
                "graph_type": "functional_traceability_graph",
                "requirement": {"id": 1, "code": "REQ-1"},
                "nodes": [
                    {"id": "n", "type": "X", "label": "n", "metadata": {}}
                ],
                "edges": [
                    {
                        "source": "n",
                        "target": "n",
                        "relation": "related_to",
                        "evidence_status": "unknown",
                    }
                ],
            },
            "evidence_status inválido",
        ),
        (
            {
                "graph_type": "functional_traceability_graph",
                "requirement": "invalid",
                "nodes": [],
                "edges": [],
            },
            "grafo sem requirement válido",
        ),
        (
            {
                "graph_type": "functional_traceability_graph",
                "requirement": {"code": "REQ-1"},
                "nodes": [],
                "edges": [],
            },
            "grafo sem requirement.id",
        ),
        (
            {
                "graph_type": "functional_traceability_graph",
                "requirement": {"id": 1, "code": "REQ-1"},
                "nodes": [
                    {
                        "id": "requirement:REQ-1",
                        "type": "REQUIREMENT",
                        "label": "REQ-1",
                        "metadata": "invalid",
                    }
                ],
                "edges": [],
            },
            "metadata inválido",
        ),
        (
            {
                "graph_type": "functional_traceability_graph",
                "requirement": {"id": 1, "code": "REQ-1"},
                "nodes": [
                    {
                        "id": "requirement:REQ-1",
                        "type": "",
                        "label": "REQ-1",
                        "metadata": {},
                    }
                ],
                "edges": [],
            },
            "node incompleto",
        ),
        (
            {
                "graph_type": "functional_traceability_graph",
                "requirement": {"id": 1, "code": "REQ-1"},
                "nodes": [],
                "edges": [],
            },
            "grafo não possui rastreabilidade elegível",
        ),
    ],
)
def test_live_graph_adapter_fails_closed_on_invalid_contract(payload, message):
    with pytest.raises(ChangeImpactValidationError, match=message):
        artifacts_from_traceability_graph(payload)


def test_live_change_rejects_unknown_explicit_seed():
    graph = _live_traceability_graph_payload()

    with pytest.raises(
        ChangeImpactValidationError,
        match="seeds ausentes da rastreabilidade viva",
    ):
        analyze_live_change(
            graph,
            change_id="CHANGE-LIVE-INVALID-SEED",
            query="mudança rastreável",
            seed_artifact_ids=("unknown:seed",),
            llm_generate=None,
        )


def test_live_change_validates_required_fields():
    with pytest.raises(ChangeImpactValidationError, match="change_id e query"):
        LiveChange(change_id="", query="mudança", seed_artifact_ids=("REQ-1",))

    with pytest.raises(ChangeImpactValidationError, match="seed_artifact_id"):
        LiveChange(change_id="CHANGE-1", query="mudança", seed_artifact_ids=())
