from scripts.evaluate_backup_provider_readiness import DEFAULT_REQUIRED_SECRETS, evaluate

def _report(*, present=DEFAULT_REQUIRED_SECRETS, fly="pass", r2="pass", restic="pass"):
    return evaluate(
        required_secrets=DEFAULT_REQUIRED_SECRETS,
        present_secrets=present,
        fly_probe=fly,
        r2_probe=r2,
        restic_probe=restic,
        run_url="https://github.com/example/repo/actions/runs/1",
    )

def test_ready_requires_all_secrets_and_all_probes() -> None:
    report = _report()
    assert report["decision"] == "ready"
    assert report["ready"] is True
    assert report["missing_secret_names"] == []
    assert report["secret_values_persisted"] is False
    assert report["production_touched"] is False

def test_missing_secret_is_blocked_without_probe_success() -> None:
    report = _report(present=("FLY_API_TOKEN",), fly="skipped", r2="skipped", restic="skipped")
    assert report["decision"] == "blocked_configuration"
    assert "R2_ACCOUNT_ID" in report["missing_secret_names"]
    assert report["ready"] is False

def test_invalid_credentials_are_blocked() -> None:
    report = _report(r2="fail")
    assert report["decision"] == "blocked_credentials_or_repository"
    assert report["probes"]["r2_bucket"] == "fail"

def test_probe_pending_is_not_ready() -> None:
    report = _report(restic="skipped")
    assert report["decision"] == "probe_pending"
    assert report["ready"] is False

def test_report_never_contains_secret_values() -> None:
    report = _report()
    serialized = str(report)
    assert "secret-value" not in serialized
    assert set(report["present_secret_names"]) == set(DEFAULT_REQUIRED_SECRETS)
