from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "hosted_worker_pool_reqsys_proof.py"
SPEC = importlib.util.spec_from_file_location("hosted_worker_pool_reqsys_proof", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
proof = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(proof)


class ExitedProcess:
    def poll(self):
        return 1


def test_startup_failure_reason_exposes_only_allowlisted_code(tmp_path):
    log = tmp_path / "service.log"
    log.write_text(
        "postgresql://user:do-not-leak@example.invalid/neondb\n"
        "app.postgres_authority.AuthorityUnavailable: "
        "authority_connection_unavailable:tls_certificate\n",
        encoding="utf-8",
    )

    reason = proof.startup_failure_reason(log)

    assert reason == "worker_pool_startup_authority_connection_unavailable_tls_certificate"
    assert "do-not-leak" not in reason
    assert "example.invalid" not in reason


def test_startup_failure_reason_redacts_unknown_output(tmp_path):
    log = tmp_path / "service.log"
    log.write_text("RuntimeError: secret-value-must-not-escape\n", encoding="utf-8")

    assert proof.startup_failure_reason(log) == "worker_pool_process_exited"


def test_startup_failure_reason_rejects_adversarial_authority_prefix(tmp_path):
    log = tmp_path / "service.log"
    log.write_text(
        "RuntimeError: authority_confidential_value_123\n",
        encoding="utf-8",
    )

    reason = proof.startup_failure_reason(log)

    assert reason == "worker_pool_process_exited"
    assert "confidential" not in reason
    assert "123" not in reason


def test_startup_failure_reason_handles_missing_log(tmp_path):
    assert proof.startup_failure_reason(tmp_path / "missing.log") == "worker_pool_process_exited"


def test_wait_ready_fails_immediately_with_sanitized_startup_reason(tmp_path, monkeypatch):
    log = tmp_path / "service.log"
    log.write_text(
        "AuthorityUnavailable: authority_schema_version_mismatch\n",
        encoding="utf-8",
    )
    called = False

    def unexpected_request(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("health request must not run after process exit")

    monkeypatch.setattr(proof, "request_json", unexpected_request)

    with pytest.raises(
        proof.ProofError,
        match=r"^worker_pool_startup_authority_schema_version_mismatch$",
    ):
        proof.wait_ready("token", ExitedProcess(), log)

    assert called is False


class HealthyProcess:
    def poll(self):
        return None


def test_wait_ready_preserves_healthy_service(tmp_path, monkeypatch):
    log = tmp_path / "service.log"
    log.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        proof,
        "request_json",
        lambda *_args, **_kwargs: (
            200,
            {"status": "healthy", "storage_backend": "postgres"},
        ),
    )

    health = proof.wait_ready("token", HealthyProcess(), log)

    assert health["status"] == "healthy"
    assert health["storage_backend"] == "postgres"
