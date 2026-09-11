from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import pytest

from app.services.operational_orchestrator import (
    ManifestError,
    OperationalOrchestrator,
    OperationalStore,
    load_readiness_manifest,
)


def _manifest(path: Path) -> Path:
    payload = {
        "schema_version": "1.0.0",
        "environment": "development",
        "capabilities": {
            "excel": {
                "required": True,
                "source": "env",
                "references": ["REQSYS_TEST_EXCEL_ID"],
                "description": "Excel de teste",
            },
            "sql_server": {
                "required": True,
                "source": "static",
                "configured": True,
                "description": "Probe SQL controlado pelo teste",
            },
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_manifesto_rejeita_valor_sensivel_literal(tmp_path: Path):
    path = _manifest(tmp_path / "readiness.yaml")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["capabilities"]["excel"]["token"] = "nao-deve-ser-aceito"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ManifestError, match="campos proibidos"):
        load_readiness_manifest(path)


def test_action_queue_e_idempotente(tmp_path: Path):
    store = OperationalStore(tmp_path / "state.sqlite3")
    kwargs = {
        "source": "test",
        "project": "reqsys",
        "environment": "development",
        "action_type": "readiness_check",
        "repository": "ericson-j-santos/reqsys-v2-enterprise-real",
        "branch": "feature/test",
        "sha": "sha-001",
        "risk": "green",
        "executor": "readiness_check",
        "next_action": "validar",
        "validation": {"e2e": True},
        "payload": {"manifest": "config/test.yaml"},
    }

    first, created_first = store.enqueue(**kwargs)
    second, created_second = store.enqueue(**kwargs)

    assert created_first is True
    assert created_second is False
    assert first.action_id == second.action_id
    assert store.summary()["actions_total"] == 1


def test_readiness_positivo_gera_evidencia_independente_e_idempotente(tmp_path: Path):
    db_path = tmp_path / "state.sqlite3"
    orchestrator = OperationalOrchestrator(
        store=OperationalStore(db_path),
        manifest_path=_manifest(tmp_path / "readiness.yaml"),
        environ={"REQSYS_TEST_EXCEL_ID": "excel-configurado"},
    )

    first = orchestrator.run_cycle(sha="sha-positive", branch="feature/orchestrator")
    action = first["execution"]["action"]

    assert first["execution"]["executed"] is True
    assert first["execution"]["result"]["status"] == "ready"
    assert action["status"] == "succeeded"
    assert "excel-configurado" not in json.dumps(first, ensure_ascii=False)

    with sqlite3.connect(db_path) as independent:
        row = independent.execute(
            "SELECT COUNT(*), status, sha FROM evidence WHERE correlation_id = ?",
            (action["correlation_id"],),
        ).fetchone()
    assert row == (1, "ready", "sha-positive")

    second = orchestrator.run_cycle(sha="sha-positive", branch="feature/orchestrator")
    assert second["action_created"] is False
    assert second["execution"]["reason"] == "already_succeeded"

    with sqlite3.connect(db_path) as independent:
        evidence_count = independent.execute(
            "SELECT COUNT(*) FROM evidence WHERE correlation_id = ?",
            (action["correlation_id"],),
        ).fetchone()[0]
    assert evidence_count == 1


def test_readiness_negativo_bloqueia_e_pode_ser_revalidado(tmp_path: Path):
    db_path = tmp_path / "state.sqlite3"
    manifest = _manifest(tmp_path / "readiness.yaml")
    blocked = OperationalOrchestrator(
        store=OperationalStore(db_path),
        manifest_path=manifest,
        environ={},
    )

    first = blocked.run_cycle(sha="sha-negative", branch="feature/orchestrator")
    action = first["execution"]["action"]
    assert first["execution"]["result"]["status"] == "blocked"
    assert first["execution"]["result"]["missing_required"] == ["excel"]
    assert action["status"] == "blocked"

    ready = OperationalOrchestrator(
        store=OperationalStore(db_path),
        manifest_path=manifest,
        environ={"REQSYS_TEST_EXCEL_ID": "agora-configurado"},
    )
    second = ready.execute(action["action_id"])
    assert second["result"]["status"] == "ready"
    assert second["action"]["status"] == "succeeded"

    evidence = ready.store.list_evidence(action["correlation_id"])
    assert {item.status for item in evidence} == {"blocked", "ready"}


def test_falha_ci_entra_amarela_e_nao_autoexecuta(tmp_path: Path):
    orchestrator = OperationalOrchestrator(
        store=OperationalStore(tmp_path / "state.sqlite3"),
        manifest_path=_manifest(tmp_path / "readiness.yaml"),
        environ={"REQSYS_TEST_EXCEL_ID": "ok"},
    )
    result = orchestrator.ingest_workflow_run(
        {
            "id": 123,
            "name": "CI",
            "status": "completed",
            "conclusion": "failure",
            "head_branch": "feature/x",
            "head_sha": "sha-ci-failure",
            "html_url": "https://github.com/example/run/123",
        }
    )

    assert result["created"] is True
    action = result["action"]
    assert action["risk"] == "yellow"
    assert action["status"] == "awaiting_approval"
    assert orchestrator.execute(action["action_id"])["reason"] == "approval_required"
    assert orchestrator.execute(action["action_id"], confirm=True)["reason"] == "external_executor_required"


def test_run_saudavel_nao_cria_pendencia(tmp_path: Path):
    orchestrator = OperationalOrchestrator(
        store=OperationalStore(tmp_path / "state.sqlite3"),
        manifest_path=_manifest(tmp_path / "readiness.yaml"),
        environ={"REQSYS_TEST_EXCEL_ID": "ok"},
    )
    result = orchestrator.ingest_workflow_run(
        {"id": 7, "name": "CI", "status": "completed", "conclusion": "success"}
    )

    assert result == {"created": False, "reason": "healthy_run"}
    assert orchestrator.store.summary()["actions_total"] == 0
