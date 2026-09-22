from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.change_evidence import ChangeEvidenceRecord
from app.api.service_cases import (
    ServiceCaseEventRecord,
    ServiceCaseRecord,
    require_service_case_auth,
)
from app.core.service_tokens import ServiceAuthContext
from app.db import Base, get_db
from app.main import app
from app.models.gestao_ti import ServicoTI

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=engine)
client = TestClient(app)


def _db_override():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


def _auth_override():
    return ServiceAuthContext(ator="rsm-change-test", via_token=False)


@pytest.fixture(autouse=True)
def _overrides():
    app.dependency_overrides[get_db] = _db_override
    app.dependency_overrides[require_service_case_auth] = _auth_override
    yield
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(require_service_case_auth, None)


@pytest.fixture
def service_id() -> str:
    value = str(uuid4())
    db = TestingSession()
    try:
        db.add(
            ServicoTI(
                servico_id=value,
                codigo=f"RSM_CHANGE_{value[:8].upper()}",
                nome="Servico CHANGE evidence test",
                criticidade="media",
                responsavel_tecnico="rsm-test",
                responsavel_negocio="rsm-test",
                ativo=True,
            )
        )
        db.commit()
    finally:
        db.close()
    return value


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _create_change(service_id: str) -> dict:
    response = client.post(
        "/v1/service-cases",
        json={
            "case_type": "CHANGE",
            "service_id": service_id,
            "requester": "rsm-change-test",
            "impact": "HIGH",
            "urgency": "HIGH",
            "idempotency_key": _sha256(f"change-{uuid4()}"),
            "event_id": str(uuid4()),
            "source": "reqsys",
        },
        headers={"X-Correlation-ID": "rsm-change-create"},
    )
    assert response.status_code == 200
    return response.json()["data"]["case"]


def _transition(case: dict, target: str, *, evidence: bool = False):
    body = {
        "target_state": target,
        "expected_version": case["version"],
        "event_id": str(uuid4()),
    }
    if evidence:
        body["evidence_uri"] = f"urn:reqsys:resolution:{case['case_id']}"
        body["evidence_sha256"] = _sha256(case["case_id"])
    return client.post(
        f"/v1/service-cases/{case['case_id']}/transitions",
        json=body,
        headers={"X-Correlation-ID": "rsm-change-transition"},
    )


def _resolved_change(service_id: str) -> dict:
    case = _create_change(service_id)
    for target in ("TRIAGE", "IN_PROGRESS"):
        response = _transition(case, target)
        assert response.status_code == 200
        case = response.json()["data"]["case"]
    response = _transition(case, "RESOLVED", evidence=True)
    assert response.status_code == 200
    return response.json()["data"]["case"]


def _evidence_payload(
    head_sha: str,
    *,
    event_id: str | None = None,
    status: str = "PASSED",
    runtime_sha: str | None = None,
) -> dict:
    return {
        "event_id": event_id or str(uuid4()),
        "requirement_ref": "REQ-1789",
        "sdd_ref": "rsm-07-change-traceability",
        "pull_request_ref": "PR-RSM-07",
        "head_sha": head_sha,
        "ci_run_id": "run-rsm-07",
        "ci_conclusion": "success",
        "deployment_ref": "github-actions:deployment-rsm-07",
        "environment": "ci-e2e",
        "runtime_sha": runtime_sha or head_sha,
        "post_deploy_evidence_uri": "urn:reqsys:rsm-07:runtime",
        "post_deploy_evidence_sha256": _sha256("runtime-evidence"),
        "status": status,
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }


def test_change_cannot_close_before_runtime_evidence_and_closes_after_exact_sha(service_id):
    case = _resolved_change(service_id)

    blocked = _transition(case, "CLOSED")
    assert blocked.status_code == 409
    assert "sem evidência runtime" in blocked.json()["detail"]

    db = TestingSession()
    try:
        persisted = db.get(ServiceCaseRecord, case["case_id"])
        assert persisted is not None
        assert persisted.state == "RESOLVED"
    finally:
        db.close()

    head_sha = "a" * 40
    event_id = str(uuid4())
    payload = _evidence_payload(head_sha, event_id=event_id)
    recorded = client.post(
        f"/v1/service-cases/{case['case_id']}/change-evidence",
        json=payload,
        headers={"X-Correlation-ID": "rsm-change-evidence"},
    )
    assert recorded.status_code == 200
    assert recorded.json()["data"]["duplicate"] is False
    evidence = recorded.json()["data"]["change_evidence"]
    assert evidence["head_sha"] == head_sha
    assert evidence["runtime_sha"] == head_sha
    assert evidence["status"] == "PASSED"

    replay = client.post(
        f"/v1/service-cases/{case['case_id']}/change-evidence",
        json=payload,
        headers={"X-Correlation-ID": "rsm-change-evidence"},
    )
    assert replay.status_code == 200
    assert replay.json()["data"]["duplicate"] is True

    closed = _transition(case, "CLOSED")
    assert closed.status_code == 200
    assert closed.json()["data"]["case"]["state"] == "CLOSED"

    replay_after_close = client.post(
        f"/v1/service-cases/{case['case_id']}/change-evidence",
        json=payload,
        headers={"X-Correlation-ID": "rsm-change-evidence"},
    )
    assert replay_after_close.status_code == 200
    assert replay_after_close.json()["data"]["duplicate"] is True

    db = TestingSession()
    try:
        assert (
            db.query(ChangeEvidenceRecord)
            .filter_by(case_id=case["case_id"])
            .count()
            == 1
        )
        assert (
            db.query(ServiceCaseEventRecord)
            .filter_by(
                case_id=case["case_id"],
                event_type="CHANGE_RUNTIME_EVIDENCE_RECORDED",
            )
            .count()
            == 1
        )
    finally:
        db.close()


def test_runtime_sha_mismatch_fails_without_persistence(service_id):
    case = _resolved_change(service_id)
    payload = _evidence_payload("b" * 40, runtime_sha="c" * 40)

    response = client.post(
        f"/v1/service-cases/{case['case_id']}/change-evidence",
        json=payload,
    )
    assert response.status_code == 422
    assert "runtime SHA divergente" in response.json()["detail"]

    db = TestingSession()
    try:
        assert (
            db.query(ChangeEvidenceRecord)
            .filter_by(case_id=case["case_id"])
            .count()
            == 0
        )
    finally:
        db.close()


def test_failed_post_deploy_evidence_keeps_change_open(service_id):
    case = _resolved_change(service_id)
    payload = _evidence_payload("d" * 40, status="FAILED")

    recorded = client.post(
        f"/v1/service-cases/{case['case_id']}/change-evidence",
        json=payload,
    )
    assert recorded.status_code == 200

    blocked = _transition(case, "CLOSED")
    assert blocked.status_code == 409
    assert "rollback não foi comprovado" in blocked.json()["detail"]


def test_change_evidence_is_rejected_for_non_change_case(service_id):
    response = client.post(
        "/v1/service-cases",
        json={
            "case_type": "REQUEST",
            "service_id": service_id,
            "requester": "rsm-change-test",
            "impact": "MEDIUM",
            "urgency": "MEDIUM",
            "idempotency_key": _sha256(f"request-{uuid4()}"),
            "event_id": str(uuid4()),
            "source": "reqsys",
        },
    )
    case = response.json()["data"]["case"]
    payload = _evidence_payload("e" * 40)

    evidence = client.post(
        f"/v1/service-cases/{case['case_id']}/change-evidence",
        json=payload,
    )
    assert evidence.status_code == 409


def test_rollback_evidence_unblocks_change_after_failed_validation(service_id):
    case = _resolved_change(service_id)
    head_sha = "f" * 40

    failed_payload = _evidence_payload(head_sha, status="FAILED")
    failed_payload["observed_at"] = "2026-09-22T12:00:00+00:00"
    failed = client.post(
        f"/v1/service-cases/{case['case_id']}/change-evidence",
        json=failed_payload,
    )
    assert failed.status_code == 200

    blocked = _transition(case, "CLOSED")
    assert blocked.status_code == 409

    rollback_payload = _evidence_payload(head_sha, status="ROLLED_BACK")
    rollback_payload.update(
        {
            "observed_at": "2026-09-22T12:05:00+00:00",
            "rollback_ref": "revert:known-good",
            "rollback_runtime_sha": "1" * 40,
            "rollback_evidence_uri": "urn:reqsys:rsm-07:rollback",
            "rollback_evidence_sha256": _sha256("rollback-evidence"),
        }
    )
    rollback = client.post(
        f"/v1/service-cases/{case['case_id']}/change-evidence",
        json=rollback_payload,
    )
    assert rollback.status_code == 200
    assert rollback.json()["data"]["change_evidence"]["status"] == "ROLLED_BACK"

    closed = _transition(case, "CLOSED")
    assert closed.status_code == 200
    assert closed.json()["data"]["case"]["state"] == "CLOSED"
