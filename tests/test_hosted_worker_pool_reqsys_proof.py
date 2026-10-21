from __future__ import annotations

import importlib.util
import stat
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

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



def test_materialize_explicit_system_root_uses_private_host_bundle(tmp_path, monkeypatch):
    bundle = tmp_path / "ca-certificates.crt"
    bundle.write_text("test-ca", encoding="utf-8")
    source = tmp_path / "runtime.url"
    source.write_text(
        "postgresql://runtime:private-value@example.neon.tech/neondb"
        "?sslmode=verify-full&sslrootcert=system&channel_binding=require\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(proof, "SYSTEM_CA_BUNDLE", bundle)

    runtime = proof.materialize_explicit_system_root(
        {
            "CODEX_WORKER_POOL_DATABASE_URL_FILE": str(source),
            "EWP_TEST_POSTGRES_URL_FILE": str(source),
        },
        tmp_path,
    )

    destination = Path(runtime["CODEX_WORKER_POOL_DATABASE_URL_FILE"])
    assert runtime["EWP_TEST_POSTGRES_URL_FILE"] == str(destination)
    assert destination != source
    query = parse_qs(urlsplit(destination.read_text(encoding="utf-8").strip()).query)
    assert query["sslmode"] == ["verify-full"]
    assert query["sslrootcert"] == [str(bundle)]
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert "private-value" not in str(runtime)


def test_materialize_explicit_system_root_rejects_unexpected_profile(tmp_path, monkeypatch):
    bundle = tmp_path / "ca-certificates.crt"
    bundle.write_text("test-ca", encoding="utf-8")
    source = tmp_path / "runtime.url"
    source.write_text(
        "postgresql://runtime:private-value@example.neon.tech/neondb"
        "?sslmode=verify-full&sslrootcert=/tmp/untrusted.pem\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(proof, "SYSTEM_CA_BUNDLE", bundle)

    with pytest.raises(proof.ProofError, match=r"^runtime_tls_profile_invalid$"):
        proof.materialize_explicit_system_root(
            {
                "CODEX_WORKER_POOL_DATABASE_URL_FILE": str(source),
                "EWP_TEST_POSTGRES_URL_FILE": str(source),
            },
            tmp_path,
        )



def test_work_request_delegates_safe_branch_derivation_to_work_v1():
    request = proof.work_request(
        proof.argparse.Namespace(
            issue_number=2020,
            request_id="request-123",
            correlation_id="correlation-123",
            base_sha="a" * 40,
        )
    )

    assert request["repository"] == proof.REPOSITORY
    assert request["request_id"] == proof.base_bound_work_request_id(
        "request-123", "a" * 40
    )
    assert request["request_id"] != "request-123"
    assert request["fencing_required"] is True
    assert request["merge_policy"] == "governed"
    assert "target_branch" not in request
    assert "main" not in request.values()



def test_work_request_identity_is_stable_per_base_and_changes_across_bases():
    first = proof.base_bound_work_request_id("gateway-request", "a" * 40)
    replay = proof.base_bound_work_request_id("gateway-request", "a" * 40)
    advanced = proof.base_bound_work_request_id("gateway-request", "b" * 40)

    assert first == replay
    assert first != advanced
    assert first.startswith("reqsys-")
    assert len(first) == 71


def test_work_request_identity_rejects_invalid_base_sha():
    with pytest.raises(proof.ProofError, match=r"^work_request_identity_invalid$"):
        proof.base_bound_work_request_id("gateway-request", "main")


def test_run_task_forwards_private_runtime_environment(tmp_path, monkeypatch):
    observed = {}
    monkeypatch.setenv("AMBIENT_CONTEXT", "preserved")

    class Completed:
        returncode = 0
        stdout = '{"result":"ok"}\n'

    def fake_run(*_args, **kwargs):
        observed.update(kwargs["env"])
        return Completed()

    monkeypatch.setattr(proof.subprocess, "run", fake_run)

    result = proof.run_task(
        tmp_path,
        ["provider-readback"],
        environment={"CODEX_WORKER_POOL_DATABASE_URL_FILE": "/private/runtime.url"},
    )

    assert result == {"result": "ok"}
    assert observed["AMBIENT_CONTEXT"] == "preserved"
    assert observed["CODEX_WORKER_POOL_DATABASE_URL_FILE"] == "/private/runtime.url"


def test_existing_verified_work_requires_all_independent_controls():
    work = {
        "evidence": {
            "state": "verified",
            "validation_sha": "a" * 40,
            "independent_readback": True,
            "positive_control": True,
            "negative_control": True,
        },
        "merge": {"state": "ready", "expected_head_sha": "a" * 40},
    }

    assert proof.existing_verified_work(work, "a" * 40) is True

    work["evidence"]["independent_readback"] = False
    with pytest.raises(proof.ProofError, match=r"^existing_work_evidence_invalid$"):
        proof.existing_verified_work(work, "a" * 40)


def test_pending_work_evidence_is_not_accepted_as_verified():
    assert proof.existing_verified_work(
        {"evidence": {"state": "pending"}, "merge": {"state": "pending"}},
        "a" * 40,
    ) is False
