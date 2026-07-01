"""Testes do orquestrador artifact_ingestion_refresh."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_trilha_d_history import artifact_ingestion_refresh_surface_ready
from scripts.refresh_trilha_d_artifact_ingestion import _run_retryable, refresh_artifacts


def _sample_report() -> dict:
    return {
        "state": "green",
        "decision": "permitir",
        "average_score": 97.5,
        "parallelizable": True,
        "dimensions": [
            {"dimension": "tests", "status": "passed", "score": 100.0, "summary": "ok"},
            {"dimension": "coverage", "status": "passed", "score": 88.0, "summary": "ok"},
            {"dimension": "mutation", "status": "passed", "score": 100.0, "summary": "ok"},
            {"dimension": "contract", "status": "passed", "score": 100.0, "summary": "ok"},
            {"dimension": "schema", "status": "passed", "score": 100.0, "summary": "ok"},
            {"dimension": "ci-watch", "status": "passed", "score": 100.0, "summary": "ok"},
        ],
    }


def test_artifact_ingestion_refresh_surface_ready_detecta_arquivos() -> None:
    assert artifact_ingestion_refresh_surface_ready() is True


def test_refresh_artifacts_atualiza_jsons_downstream(tmp_path: Path) -> None:
    repo_root = tmp_path
    report_path = repo_root / "artifacts/trilha-d-qualidade-governanca/trilha-d-qualidade-governanca.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(_sample_report()), encoding="utf-8")

    (repo_root / "docs/ops-dashboard/data").mkdir(parents=True, exist_ok=True)

    result = refresh_artifacts(
        report_path,
        repo_root=repo_root,
        github_run_id="12345",
        skip_merge_readiness=True,
    )

    assert result["ok"] is True
    assert result["artifact_ingestion_refresh_enabled"] is True
    assert (repo_root / "docs/ops-dashboard/data/trilha-d-history.json").exists()
    assert (repo_root / "docs/ops-dashboard/data/padrao-ouro-operational-pareto.json").exists()
    assert (repo_root / "docs/ops-dashboard/data/predictive-regression-gate.json").exists()
    assert (repo_root / "docs/ops-dashboard/data/continuous-trilha-d-monitoring.json").exists()
    assert (repo_root / "docs/ops-dashboard/data/continuous-trilha-d-monitoring-history.json").exists()
    assert (repo_root / "docs/ops-dashboard/data/governance-evidence-index.json").exists()


def test_refresh_artifacts_eh_idempotente_quando_reexecutado(tmp_path: Path) -> None:
    repo_root = tmp_path
    report_path = repo_root / "artifacts/trilha-d-qualidade-governanca/trilha-d-qualidade-governanca.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(_sample_report()), encoding="utf-8")
    (repo_root / "docs/ops-dashboard/data").mkdir(parents=True, exist_ok=True)

    first = refresh_artifacts(report_path, repo_root=repo_root, github_run_id="12345", skip_merge_readiness=True)
    second = refresh_artifacts(report_path, repo_root=repo_root, github_run_id="12345", skip_merge_readiness=True)

    assert first["ok"] is True
    assert second["ok"] is True
    assert second["artifact_ingestion_refresh_enabled"] is True


def test_refresh_retryable_recupera_falha_transitoria(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = {"count": 0}

    def flaky_operation() -> str:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("io transitorio")
        return "ok"

    monkeypatch.setattr("scripts.refresh_trilha_d_artifact_ingestion.time.sleep", lambda _: None)

    assert _run_retryable("flaky", flaky_operation, attempts=2) == "ok"
    assert attempts["count"] == 2


def test_refresh_retryable_preserva_erro_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scripts.refresh_trilha_d_artifact_ingestion.time.sleep", lambda _: None)

    with pytest.raises(RuntimeError, match="fatal falhou após 2 tentativas"):
        _run_retryable("fatal", lambda: (_ for _ in ()).throw(ValueError("schema invalido")), attempts=2)


def test_refresh_artifacts_falha_sem_relatorio(tmp_path: Path) -> None:
    result = refresh_artifacts(tmp_path / "missing.json", repo_root=tmp_path)
    assert result["ok"] is False
    assert result["error"] == "report_missing"
