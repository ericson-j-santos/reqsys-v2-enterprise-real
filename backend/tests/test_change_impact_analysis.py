import json
from pathlib import Path

import pytest

from app.services.change_impact_analysis import (
    ChangeImpactValidationError,
    HistoricalChange,
    ImpactArtifact,
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
