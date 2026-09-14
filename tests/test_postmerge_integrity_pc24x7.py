from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


capture = load_module("capture_pc24x7_runtime_evidence", "scripts/capture_pc24x7_runtime_evidence.py")
resolver = load_module("resolve_runtime_evidence_provider", "scripts/resolve_runtime_evidence_provider.py")
publication = load_module("validate_publication_sync_pc24x7", "scripts/validate_publication_sync.py")


def healthy_results():
    return [
        {"endpoint": endpoint, "ok": True, "status_code": 200, "elapsed_ms": 5}
        for endpoint in capture.REQUIRED_ENDPOINTS
    ]


def evidence(now: datetime, sha: str = "abc123"):
    return capture.build_evidence(
        source_commit=sha,
        expected_sha=sha,
        base_url="http://localhost:8081",
        results=healthy_results(),
        generated_at=now,
    )


def test_pc24x7_capture_is_ready_only_with_runtime_and_same_sha():
    now = datetime(2026, 9, 14, 22, 0, tzinfo=UTC)
    ok = evidence(now)
    assert ok["ready"] is True
    assert ok["runtime_ready"] is True
    assert ok["same_sha"] is True
    assert ok["provider"] == "pc24x7"
    assert ok["environment"] == "dev"

    bad_runtime = capture.build_evidence(
        source_commit="abc123",
        expected_sha="abc123",
        base_url="http://localhost:8081",
        results=[{"endpoint": "/api/health", "ok": False}],
        generated_at=now,
    )
    assert bad_runtime["ready"] is False

    wrong_sha = capture.build_evidence(
        source_commit="oldsha",
        expected_sha="abc123",
        base_url="http://localhost:8081",
        results=healthy_results(),
        generated_at=now,
    )
    assert wrong_sha["ready"] is False
    assert wrong_sha["same_sha"] is False


def test_dev_pc24x7_requires_fresh_same_sha_evidence():
    now = datetime(2026, 9, 14, 22, 0, tzinfo=UTC)
    current = evidence(now)
    result = resolver.resolve_provider(
        "dev",
        "pc24x7",
        expected_sha="abc123",
        evidence=current,
        now=now,
    )
    assert result == {
        "allowed": True,
        "environment": "dev",
        "provider": "pc24x7",
        "findings": [],
    }

    stale = evidence(now - timedelta(minutes=16))
    result = resolver.resolve_provider(
        "dev",
        "pc24x7",
        expected_sha="abc123",
        evidence=stale,
        now=now,
    )
    assert result["allowed"] is False
    assert "evidence_stale" in result["findings"]

    mismatch = evidence(now, sha="oldsha")
    result = resolver.resolve_provider(
        "dev",
        "pc24x7",
        expected_sha="abc123",
        evidence=mismatch,
        now=now,
    )
    assert result["allowed"] is False
    assert "source_commit_mismatch" in result["findings"]


def test_pc24x7_missing_evidence_fails_closed_and_fly_is_explicit_transition():
    missing = resolver.resolve_provider(
        "dev",
        "pc24x7",
        expected_sha="abc123",
        evidence=None,
    )
    assert missing["allowed"] is False
    assert missing["findings"] == ["pc24x7_evidence_missing"]

    fly = resolver.resolve_provider("dev", "fly", expected_sha="abc123")
    assert fly["allowed"] is True
    assert fly["provider"] == "fly"
    assert fly["findings"] == ["transitional_fly_provider"]


def test_pc24x7_is_rejected_outside_dev():
    for environment in ("stg", "prod"):
        result = resolver.resolve_provider(
            environment,
            "pc24x7",
            expected_sha="abc123",
        )
        assert result["allowed"] is False
        assert result["findings"] == ["pc24x7_not_allowed_outside_dev"]


def test_publication_validator_accepts_custom_health_path_without_weakening_sha(monkeypatch):
    json_calls: list[str] = []
    text_calls: list[str] = []

    def fake_json(url: str, timeout: float):
        json_calls.append(url)
        if url.endswith("/api/runtime/build-info"):
            return {"build_sha": "abc123"}, None
        if url.endswith("/api/runtime/version"):
            return {"version": "1.2.3"}, None
        if url.endswith("/api/health"):
            return {"status": "ok"}, None
        raise AssertionError(url)

    def fake_text(url: str, timeout: float):
        text_calls.append(url)
        return "<html><script src='/assets/index-demo.js'></script></html>", None

    monkeypatch.setattr(publication, "_http_json", fake_json)
    monkeypatch.setattr(publication, "_http_text", fake_text)
    monkeypatch.setattr(publication, "_http_head_last_modified", lambda url, timeout: ("now", None))

    result = publication.validate_environment(
        "dev",
        {
            "api_url": "https://pc24x7.example.test",
            "frontend_url": "https://pc24x7.example.test",
            "health_path": "/api/health",
        },
        expected_sha="abc123",
        expected_version="1.2.3",
        timeout=1,
    )

    assert result["synced"] is True
    assert result["health_path"] == "/api/health"
    assert "https://pc24x7.example.test/api/health" in json_calls
    assert text_calls == ["https://pc24x7.example.test/"]


def test_publication_validator_keeps_fly_health_default(monkeypatch):
    json_calls: list[str] = []

    def fake_json(url: str, timeout: float):
        json_calls.append(url)
        if url.endswith("/api/runtime/build-info"):
            return {"build_sha": "abc123"}, None
        if url.endswith("/api/runtime/version"):
            return {"version": "1.2.3"}, None
        if url.endswith("/health"):
            return {"status": "ok"}, None
        raise AssertionError(url)

    monkeypatch.setattr(publication, "_http_json", fake_json)

    result = publication.validate_environment(
        "dev",
        {"api_url": "https://fly.example.test", "frontend_required": False},
        expected_sha="abc123",
        expected_version="1.2.3",
        timeout=1,
    )

    assert result["synced"] is True
    assert result["health_path"] == "/health"
    assert "https://fly.example.test/health" in json_calls


def test_bacen_workflow_uses_policy_dates_instead_of_fixed_historical_date():
    workflow = (ROOT / ".github/workflows/bacen-nonprod-tolerance-guard.yml").read_text(
        encoding="utf-8"
    )
    assert 'evidence["valid_until"] == "2026-08-29"' not in workflow
    assert 'policy["activation"]' in workflow
    assert 'expected_valid_until = str(activation["valid_until"])' in workflow
    assert 'today <= date.fromisoformat(evidence["valid_until"])' in workflow


def test_automatic_promotion_routes_dev_provider_without_self_hosted_runner():
    workflow = (ROOT / ".github/workflows/fly-automatic-environment-promotion.yml").read_text(
        encoding="utf-8"
    )
    assert "REQSYS_DEV_RUNTIME_PROVIDER" in workflow
    assert "PC24X7_DEV_BASE_URL" in workflow
    assert "PC24X7_DEV_FRONTEND_URL" in workflow
    assert "validate-dev-pc24x7:" in workflow
    assert "runs-on: ubuntu-latest" in workflow
    assert "runs-on: self-hosted" not in workflow
    assert "dev_provider == 'pc24x7'" in workflow
    assert "dev_provider == 'fly'" in workflow
    assert '"health_path": "/api/health"' in workflow
    assert "/api/runtime/health" in workflow
    assert "pc24x7_externally_verified" in workflow
    assert "pc24x7_validation_failed" in workflow
