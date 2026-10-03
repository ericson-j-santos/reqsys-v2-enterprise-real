from scripts.evaluate_backup_provider_readiness import (
    DEFAULT_REQUIRED_SECRETS,
    evaluate,
)


def _report(*, present=DEFAULT_REQUIRED_SECRETS, r2="pass", restic="pass"):
    return evaluate(
        required_secrets=DEFAULT_REQUIRED_SECRETS,
        present_secrets=present,
        r2_probe=r2,
        restic_probe=restic,
        run_url="https://github.com/example/repo/actions/runs/1",
    )


def test_ready_requires_all_backup_secrets_and_probes():
    report = _report()
    assert report["decision"] == "ready"
    assert report["ready"] is True
    assert report["missing_secret_names"] == []
    assert report["secret_values_persisted"] is False
    assert report["production_touched"] is False
    assert "FLY_API_TOKEN" not in report["required_secret_names"]
    assert "fly" not in report["probes"]


def test_missing_secret_blocks_readiness():
    report = _report(present=("R2_ACCOUNT_ID",), r2="skipped", restic="skipped")
    assert report["decision"] == "blocked_configuration"
    assert "R2_BUCKET" in report["missing_secret_names"]
    assert report["ready"] is False


def test_invalid_credentials_are_blocked():
    report = _report(r2="fail")
    assert report["decision"] == "blocked_credentials_or_repository"
    assert report["probes"]["r2_bucket"] == "fail"


def test_probe_pending_is_not_ready():
    report = _report(restic="skipped")
    assert report["decision"] == "probe_pending"
    assert report["ready"] is False


def test_report_never_contains_secret_values():
    report = _report()
    assert "secret-value" not in str(report)
    assert set(report["present_secret_names"]) == set(DEFAULT_REQUIRED_SECRETS)
