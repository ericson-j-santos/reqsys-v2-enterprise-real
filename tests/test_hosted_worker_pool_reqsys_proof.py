from __future__ import annotations

import importlib.util
import stat
from pathlib import Path
from types import SimpleNamespace

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


class FakeCABundle:
    def __init__(self, *, mode: int = stat.S_IFREG | 0o644,
                 owner: int = 0, size: int = 1024, missing: bool = False) -> None:
        self.mode, self.owner, self.size, self.missing = mode, owner, size, missing

    def lstat(self):
        if self.missing:
            raise FileNotFoundError("test-bundle")
        return SimpleNamespace(st_mode=self.mode, st_uid=self.owner, st_size=self.size)

    def __str__(self) -> str:
        return "/etc/ssl/certs/ca-certificates.crt"


def test_system_ca_bundle_qualified_preserves_strict_tls_and_replay() -> None:
    env = {
        "SSL_CERT_FILE": "/tmp/untrusted.crt",
        "SSL_CERT_DIR": "/tmp/untrusted",
        "PGSSLMODE": "verify-full",
        "PGSSLROOTCERT": "system",
    }
    qualified = FakeCABundle()

    proof.configure_system_ca_bundle(env, bundle=qualified)
    snapshot = dict(env)
    proof.configure_system_ca_bundle(env, bundle=qualified)

    assert env == snapshot
    assert env["SSL_CERT_FILE"] == "/etc/ssl/certs/ca-certificates.crt"
    assert "SSL_CERT_DIR" not in env
    assert env["PGSSLMODE"] == "verify-full"
    assert env["PGSSLROOTCERT"] == "system"


@pytest.mark.parametrize(
    ("bundle", "reason"),
    [
        (FakeCABundle(mode=stat.S_IFLNK | 0o777), "hosted_ca_bundle_unqualified"),
        (FakeCABundle(mode=stat.S_IFDIR | 0o755), "hosted_ca_bundle_unqualified"),
        (FakeCABundle(mode=stat.S_IFREG | 0o666), "hosted_ca_bundle_unqualified"),
        (FakeCABundle(owner=1000), "hosted_ca_bundle_unqualified"),
        (FakeCABundle(size=0), "hosted_ca_bundle_unqualified"),
        (FakeCABundle(size=10000001), "hosted_ca_bundle_unqualified"),
        (FakeCABundle(missing=True), "hosted_ca_bundle_unavailable"),
    ],
)
def test_system_ca_bundle_blocks_untrusted_input_without_mutating_env(
    bundle, reason: str
) -> None:
    env = {"SSL_CERT_FILE": "/tmp/original.crt", "SSL_CERT_DIR": "/tmp/original"}

    with pytest.raises(proof.ProofError, match=rf"^{reason}$"):
        proof.configure_system_ca_bundle(env, bundle=bundle)

    assert env == {"SSL_CERT_FILE": "/tmp/original.crt", "SSL_CERT_DIR": "/tmp/original"}
