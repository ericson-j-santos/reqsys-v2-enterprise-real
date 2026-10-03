from __future__ import annotations

from scripts.check_gitops_runtime_governance import validate_evidence


def _valid_payload() -> dict[str, dict[str, str]]:
    return {
        "intencao": {"status": "passed", "evidencia": "PR aprovado com escopo e risco"},
        "mudanca_git": {"status": "passed", "evidencia": "commit/versionamento rastreável"},
        "execucao": {"status": "passed", "evidencia": "sync/deploy aplicado no ambiente alvo"},
        "observabilidade": {"status": "passed", "evidencia": "health check, logs, métricas ou traces"},
        "recuperacao": {"status": "passed", "evidencia": "rollback ou plano de recuperação validável"},
    }


def test_validate_evidence_passes_when_all_layers_have_runtime_evidence() -> None:
    result = validate_evidence(_valid_payload())

    assert result.status == "passed"
    assert result.risk == "low"
    assert result.missing_sections == []
    assert result.failed_sections == []
    assert result.warnings == []


def test_validate_evidence_blocks_when_runtime_observability_is_missing() -> None:
    payload = _valid_payload()
    payload.pop("observabilidade")

    result = validate_evidence(payload)

    assert result.status == "failed"
    assert result.risk == "high"
    assert result.missing_sections == ["observabilidade"]


def test_validate_evidence_blocks_when_recovery_failed() -> None:
    payload = _valid_payload()
    payload["recuperacao"] = {"status": "failed", "evidencia": "rollback não validado"}

    result = validate_evidence(payload)

    assert result.status == "failed"
    assert result.risk == "high"
    assert result.failed_sections == ["recuperacao"]


def test_validate_evidence_warns_when_green_without_evidence() -> None:
    payload = _valid_payload()
    payload["execucao"] = {"status": "passed"}

    result = validate_evidence(payload)

    assert result.status == "warning"
    assert result.risk == "medium"
    assert "Seção execucao marcada como verde sem campo evidencia" in result.warnings
