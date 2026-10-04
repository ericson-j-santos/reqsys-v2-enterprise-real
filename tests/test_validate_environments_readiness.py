import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.validate_environments_readiness import (  # noqa: E402
    EnvironmentTarget,
    classify_environment,
    is_local_url,
    parse_environment_target,
    validate_all_environments,
)


def test_parse_environment_target_uses_explicit_provider_neutral_urls() -> None:
    target = parse_environment_target(
        "dev=https://app-dev.example.net,https://api-dev.example.net/docs"
    )

    assert target.canonical == "dev"
    assert target.frontend == "https://app-dev.example.net"
    assert target.api == "https://api-dev.example.net/docs"
    assert "provider-neutral" in target.notes


def test_parse_environment_target_rejects_retired_provider() -> None:
    with pytest.raises(ValueError, match="retirado definitivamente"):
        parse_environment_target(
            "dev=https://legacy.fly.dev,https://api-dev.example.net/docs"
        )


def test_local_urls_are_detected() -> None:
    assert is_local_url("http://localhost:8084") is True
    assert is_local_url("http://127.0.0.1:8212/docs") is True
    assert is_local_url("https://app.example.net") is False


def test_classify_environment_ready_when_remote_checks_are_ok() -> None:
    result = classify_environment(
        {"ok": True, "mode": "remote_probe"},
        {"ok": True, "mode": "remote_probe"},
    )

    assert result["status"] == "ready"
    assert result["operational_risk"] == "low"
    assert result["readiness_percent"] == 100


def test_classify_environment_local_only_when_all_checks_are_skipped() -> None:
    result = classify_environment(
        {"ok": False, "mode": "local_skipped"},
        {"ok": False, "mode": "local_skipped"},
    )

    assert result["status"] == "local_only"
    assert result["operational_risk"] == "medium"
    assert result["skipped_checks"] == 2


def test_validate_all_environments_contract(monkeypatch) -> None:
    def fake_probe(url: str, timeout_seconds: float, skip_local: bool = True):
        if "localhost" in url:
            return {"url": url, "ok": False, "mode": "local_skipped"}
        return {"url": url, "ok": True, "mode": "remote_probe", "status_code": 200}

    monkeypatch.setattr("scripts.validate_environments_readiness.probe_url", fake_probe)
    targets = [
        EnvironmentTarget(
            name=name,
            canonical=name,
            frontend=f"https://app-{name}.example.net",
            api=f"https://api-{name}.example.net/docs",
            notes="explicit",
        )
        for name in ("dev", "hml", "prod")
    ]
    payload = validate_all_environments(targets)

    assert payload["schema_version"] == "1.0.0"
    assert payload["contract"] == "all-environments-readiness-validation"
    assert payload["summary"]["environments_total"] == 3
    assert payload["summary"]["ready"] == 3
    assert payload["summary"]["local_only"] == 0
    assert "ci_should_fail_only_on_contract_errors" in payload["guardrails"]


def test_validate_all_environments_rejects_all_invalid_targets_before_probe(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        "scripts.validate_environments_readiness.probe_url",
        lambda url, *_args, **_kwargs: calls.append(url),
    )
    targets = [
        EnvironmentTarget("dev", "https://app.example.net", "https://api.example.net/docs", ""),
        EnvironmentTarget("prod", "https://legacy.fly.dev", "https://api.example.net/docs", ""),
    ]

    with pytest.raises(ValueError, match="retirado definitivamente"):
        validate_all_environments(targets)

    assert calls == []
