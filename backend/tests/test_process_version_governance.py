from pathlib import Path

import pytest

from app.services.process_artifact_repository import VersionedProcessArtifactRepository
from app.services.process_version_governance import (
    ProcessPromotionConflictError,
    ProcessPromotionValidationError,
    ProcessVersionGovernanceService,
)


def _artifact(version: str, content_hash: str = "a" * 64) -> dict:
    return {
        "process_id": "approval_flow",
        "process_name": "Aprovacao",
        "process_version": version,
        "content_hash": content_hash,
        "generated_at": "2026-07-16T18:00:00+00:00",
        "correlation_id": "seed",
        "metrics": {"nodes": 2, "edges": 1, "decisions": 0},
        "definition": {
            "process_id": "approval_flow",
            "name": "Aprovacao",
            "version": version,
            "nodes": [
                {"id": "start", "name": "Inicio", "type": "start", "metadata": {}},
                {"id": "end", "name": "Fim", "type": "end", "metadata": {}},
            ],
            "edges": [{"source": "start", "target": "end", "label": None}],
        },
        "formats": {
            "mermaid": "flowchart TD\nstart --> end",
            "bpmn_2_0_xml": "<definitions />",
        },
    }


def test_promote_creates_immutable_revision_active_pointer_and_audit(tmp_path: Path):
    repository = VersionedProcessArtifactRepository(tmp_path)
    source = repository.save(_artifact("1.0.0"))
    service = ProcessVersionGovernanceService(repository)

    result = service.promote(
        process_id="approval_flow",
        source_revision=source.revision,
        target_version="1.1.0",
        actor="admin@empresa.com",
        reason="Promocao homologada",
        correlation_id="corr-123",
    )

    assert result["status"] == "promoted"
    assert result["artifact"]["revision"].startswith("1.1.0-")
    active = service.get_active("approval_flow")
    assert active["active_revision"] == result["artifact"]["revision"]
    assert active["source_revision"] == source.revision
    events = service.list_events("approval_flow")
    assert len(events) == 1
    assert events[0]["actor"] == "admin@empresa.com"
    restored = repository.get_version("approval_flow", result["artifact"]["revision"])
    assert restored["definition"]["version"] == "1.1.0"
    assert restored["formats"]["mermaid"] == "flowchart TD\nstart --> end"


def test_promote_rejects_stale_expected_current_revision(tmp_path: Path):
    repository = VersionedProcessArtifactRepository(tmp_path)
    source = repository.save(_artifact("1.0.0"))
    service = ProcessVersionGovernanceService(repository)
    first = service.promote(
        process_id="approval_flow",
        source_revision=source.revision,
        target_version="1.1.0",
        actor="admin",
        reason="Primeira promocao",
        correlation_id="corr-1",
    )

    with pytest.raises(ProcessPromotionConflictError, match="revisao ativa divergente"):
        service.promote(
            process_id="approval_flow",
            source_revision=source.revision,
            target_version="1.2.0",
            actor="admin",
            reason="Promocao concorrente",
            correlation_id="corr-2",
            expected_current_revision="revisao-desatualizada",
        )

    assert service.get_active("approval_flow")["active_revision"] == first["artifact"]["revision"]
    assert len(service.list_events("approval_flow")) == 1


def test_restore_is_non_destructive_and_keeps_previous_versions(tmp_path: Path):
    repository = VersionedProcessArtifactRepository(tmp_path)
    v1 = repository.save(_artifact("1.0.0", "a" * 64))
    v2 = repository.save(_artifact("2.0.0", "b" * 64))
    service = ProcessVersionGovernanceService(repository)

    service.promote(
        process_id="approval_flow",
        source_revision=v2.revision,
        target_version="2.0.0-active",
        actor="release-bot",
        reason="Ativacao da versao 2",
        correlation_id="corr-v2",
    )
    rollback = service.promote(
        process_id="approval_flow",
        source_revision=v1.revision,
        target_version="2.0.1-rollback",
        actor="incident-manager",
        reason="Rollback apos incidente",
        correlation_id="corr-rollback",
        expected_current_revision=service.get_active("approval_flow")["active_revision"],
    )

    revisions = {item["revision"] for item in repository.list_versions("approval_flow")}
    assert v1.revision in revisions
    assert v2.revision in revisions
    assert rollback["artifact"]["revision"] in revisions
    assert service.get_active("approval_flow")["active_revision"] == rollback["artifact"]["revision"]
    assert len(service.list_events("approval_flow")) == 2


def test_promote_validates_actor_reason_and_correlation(tmp_path: Path):
    repository = VersionedProcessArtifactRepository(tmp_path)
    source = repository.save(_artifact("1.0.0"))
    service = ProcessVersionGovernanceService(repository)

    with pytest.raises(ProcessPromotionValidationError, match="actor e obrigatorio"):
        service.promote(
            process_id="approval_flow",
            source_revision=source.revision,
            target_version="1.1.0",
            actor=" ",
            reason="Promocao",
            correlation_id="corr",
        )
