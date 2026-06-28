from scripts.validate_environments_readiness import ENVIRONMENTS, classify_environment, is_local_url, validate_all_environments


def test_all_canonical_environments_are_declared() -> None:
    names = {target.name for target in ENVIRONMENTS}

    assert names == {"desenvolvimento", "testes", "homologacao", "producao"}
    assert any(target.frontend == "https://reqsys-app-dev.fly.dev" for target in ENVIRONMENTS)
    assert any(target.api == "https://reqsys-api-dev.fly.dev/docs" for target in ENVIRONMENTS)
    assert any(target.frontend == "https://reqsys-web-stg.fly.dev" for target in ENVIRONMENTS)
    assert any(target.frontend == "https://reqsys-app.fly.dev" for target in ENVIRONMENTS)


def test_local_urls_are_detected() -> None:
    assert is_local_url("http://localhost:8084") is True
    assert is_local_url("http://127.0.0.1:8212/docs") is True
    assert is_local_url("https://reqsys-app.fly.dev") is False


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
    payload = validate_all_environments()

    assert payload["schema_version"] == "1.0.0"
    assert payload["contract"] == "all-environments-readiness-validation"
    assert payload["summary"]["environments_total"] == 4
    assert payload["summary"]["ready"] == 3
    assert payload["summary"]["local_only"] == 1
    assert "ci_should_fail_only_on_contract_errors" in payload["guardrails"]
