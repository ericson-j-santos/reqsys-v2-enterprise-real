from pathlib import Path

import pytest

from app.services.process_artifact_repository import (
    ProcessArtifactComparisonError,
    ProcessArtifactNotFoundError,
    VersionedProcessArtifactRepository,
)


def _artifact(version: str, content_hash: str, nodes: list[dict], edges: list[dict]) -> dict:
    return {
        "process_id": "approval_flow",
        "process_name": "Aprovacao de requisito",
        "process_version": version,
        "content_hash": content_hash,
        "generated_at": f"2026-07-16T12:00:0{version[-1]}+00:00",
        "correlation_id": f"test-{version}",
        "metrics": {"nodes": len(nodes), "edges": len(edges), "decisions": 0},
        "definition": {
            "process_id": "approval_flow",
            "name": "Aprovacao de requisito",
            "version": version,
            "nodes": nodes,
            "edges": edges,
        },
        "formats": {
            "mermaid": f"flowchart TD\n  start --> end_{version}",
            "bpmn_2_0_xml": f"<definitions version=\"{version}\" />",
        },
    }


def test_lists_and_retrieves_persisted_versions(tmp_path: Path):
    repository = VersionedProcessArtifactRepository(tmp_path)
    persisted = repository.save(
        _artifact(
            "1.0.0",
            "a" * 64,
            [
                {"id": "start", "name": "Inicio", "type": "start", "metadata": {}},
                {"id": "end", "name": "Fim", "type": "end", "metadata": {}},
            ],
            [{"source": "start", "target": "end", "label": None}],
        )
    )

    versions = repository.list_versions("approval_flow")
    recovered = repository.get_version("approval_flow", persisted.revision)

    assert len(versions) == 1
    assert versions[0]["revision"] == persisted.revision
    assert recovered["definition"]["nodes"][0]["id"] == "start"
    assert "flowchart TD" in recovered["formats"]["mermaid"]
    assert recovered["persistence"]["directory"].endswith(persisted.revision)


def test_structural_diff_detects_added_removed_and_changed_elements(tmp_path: Path):
    repository = VersionedProcessArtifactRepository(tmp_path)
    base = repository.save(
        _artifact(
            "1.0.0",
            "a" * 64,
            [
                {"id": "start", "name": "Inicio", "type": "start", "metadata": {}},
                {"id": "review", "name": "Revisar", "type": "task", "metadata": {}},
                {"id": "end", "name": "Fim", "type": "end", "metadata": {}},
            ],
            [
                {"source": "start", "target": "review", "label": None},
                {"source": "review", "target": "end", "label": None},
            ],
        )
    )
    target = repository.save(
        _artifact(
            "1.1.0",
            "b" * 64,
            [
                {"id": "start", "name": "Inicio", "type": "start", "metadata": {}},
                {"id": "review", "name": "Revisar e aprovar", "type": "task", "metadata": {}},
                {"id": "publish", "name": "Publicar", "type": "task", "metadata": {}},
                {"id": "end", "name": "Fim", "type": "end", "metadata": {}},
            ],
            [
                {"source": "start", "target": "review", "label": None},
                {"source": "review", "target": "publish", "label": "aprovado"},
                {"source": "publish", "target": "end", "label": None},
            ],
        )
    )

    comparison = repository.compare_versions("approval_flow", base.revision, target.revision)

    assert comparison["has_changes"] is True
    assert comparison["total_changes"] == 5
    assert [item["id"] for item in comparison["diff"]["nodes"]["added"]] == ["publish"]
    assert comparison["diff"]["nodes"]["changed"][0]["id"] == "review"
    assert len(comparison["diff"]["edges"]["added"]) == 2
    assert len(comparison["diff"]["edges"]["removed"]) == 1


def test_get_version_rejects_unknown_revision(tmp_path: Path):
    repository = VersionedProcessArtifactRepository(tmp_path)

    with pytest.raises(ProcessArtifactNotFoundError, match="revisao nao encontrada"):
        repository.get_version("approval_flow", "missing")


def test_compare_rejects_legacy_revision_without_definition(tmp_path: Path):
    repository = VersionedProcessArtifactRepository(tmp_path)
    legacy = _artifact("1.0.0", "a" * 64, [], [])
    legacy.pop("definition")
    current = _artifact("1.1.0", "b" * 64, [], [])
    base = repository.save(legacy)
    target = repository.save(current)

    with pytest.raises(ProcessArtifactComparisonError, match="snapshot estrutural"):
        repository.compare_versions("approval_flow", base.revision, target.revision)
