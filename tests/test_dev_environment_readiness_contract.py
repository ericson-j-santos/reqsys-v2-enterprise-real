import json
import subprocess
import sys
from pathlib import Path

from scripts import validate_dev_environment_readiness as validator


def test_dev_target_uses_public_https_urls():
    assert validator.is_public_https_url(validator.DEV_TARGET.frontend)
    assert validator.is_public_https_url(validator.DEV_TARGET.api_docs)
    assert validator.is_public_https_url(validator.DEV_TARGET.api_health)


def test_classify_dev_environment_ready():
    payload = validator.classify_dev_environment(
        {
            "frontend": {"ok": True},
            "api_docs": {"ok": True},
            "api_health": {"ok": True},
        }
    )

    assert payload["status"] == "ready"
    assert payload["operational_risk"] == "low"
    assert payload["readiness_percent"] == 100.0
    assert payload["recommended_action"] == "manter_monitoramento"


def test_classify_dev_environment_degraded():
    payload = validator.classify_dev_environment(
        {
            "frontend": {"ok": True},
            "api_docs": {"ok": False},
            "api_health": {"ok": False},
        }
    )

    assert payload["status"] == "degraded"
    assert payload["operational_risk"] == "medium"
    assert payload["readiness_percent"] == 33.33
    assert payload["recommended_action"] == "validar_endpoints_dev_pendentes"


def test_validate_dev_environment_contract_with_stubbed_probes(monkeypatch):
    def fake_probe(url, timeout_seconds):
        return {
            "url": url,
            "ok": True,
            "status_code": 200,
            "elapsed_ms": 1,
            "content_type": "text/html",
            "mode": "remote_probe",
            "error": None,
        }

    monkeypatch.setattr(validator, "probe_url", fake_probe)
    payload = validator.validate_dev_environment(timeout_seconds=0.1)

    assert payload["schema_version"] == "1.0.0"
    assert payload["contract"] == "dev-environment-readiness-validation"
    assert payload["summary"]["overall_status"] == "ready"
    assert payload["summary"]["mode"] == "read_only_non_blocking"
    assert payload["environment"]["name"] == "desenvolvimento"
    assert set(payload["environment"]["checks"]) == {"frontend", "api_docs", "api_health"}
    assert "no_secret_required" in payload["guardrails"]
    assert "ci_should_fail_only_on_contract_errors" in payload["guardrails"]


def test_cli_writes_dev_environment_artifact(tmp_path):
    output_path = tmp_path / "dev-environments-validation.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/validate_dev_environment_readiness.py",
            "--output",
            str(output_path),
            "--timeout-seconds",
            "0.01",
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["contract"] == "dev-environment-readiness-validation"
    assert payload["environment"]["frontend"] == "https://reqsys-app-dev.fly.dev"
    assert payload["summary"]["mode"] == "read_only_non_blocking"
