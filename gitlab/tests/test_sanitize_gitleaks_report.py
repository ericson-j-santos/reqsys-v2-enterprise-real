from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "gitlab" / "scripts" / "sanitize_gitleaks_report.py"
CI_PATH = ROOT / "gitlab" / "ci" / "devsecops.yml"

SPEC = importlib.util.spec_from_file_location("sanitize_gitleaks_report", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def finding(**overrides):
    payload = {
        "RuleID": "generic-api-key",
        "File": "tests/fixtures/example.txt",
        "StartLine": 12,
        "EndLine": 12,
        "Secret": "SENTINEL_SECRET_DO_NOT_EMIT",
        "Match": "token=SENTINEL_MATCH_DO_NOT_EMIT",
        "Entropy": 4.2,
        "Fingerprint": "SENTINEL_FINGERPRINT",
        "Commit": "deadbeef",
        "Author": "Sensitive Person",
        "Email": "sensitive@example.test",
        "Message": "sensitive commit message",
        "Date": "2026-10-18",
    }
    payload.update(overrides)
    return payload


def test_sanitizer_emits_only_allowed_metadata_and_never_secret_material():
    summary = MODULE.sanitize_report([finding()])
    serialized = json.dumps(summary, ensure_ascii=False)
    logs = "\n".join(MODULE.render_log_lines(summary))
    for sentinel in (
        "SENTINEL_SECRET_DO_NOT_EMIT",
        "SENTINEL_MATCH_DO_NOT_EMIT",
        "SENTINEL_FINGERPRINT",
        "Sensitive Person",
        "sensitive@example.test",
        "sensitive commit message",
    ):
        assert sentinel not in serialized
        assert sentinel not in logs
    assert summary["finding_count"] == 1
    assert summary["findings"] == [{
        "RuleID": "generic-api-key",
        "File": "tests/fixtures/example.txt",
        "StartLine": 12,
        "EndLine": 12,
    }]
    assert summary["redaction_contract"]["sensitive_fields_emitted"] == []


def test_sanitizer_is_deterministic_and_sorts_without_source_content():
    first = finding(File="z/path.txt", StartLine=4, EndLine=5, RuleID="jwt")
    second = finding(File="a/path.txt", StartLine=8, EndLine=8, RuleID="generic-api-key")
    assert MODULE.sanitize_report([first, second]) == MODULE.sanitize_report([second, first])
    assert [item["File"] for item in MODULE.sanitize_report([first, second])["findings"]] == [
        "a/path.txt",
        "z/path.txt",
    ]


@pytest.mark.parametrize(
    "bad_file",
    ["/etc/passwd", "../secret.txt", "folder/../../secret.txt", "path\nINJECTED=1"],
)
def test_sanitizer_rejects_unsafe_or_log_injecting_paths(bad_file: str):
    with pytest.raises(MODULE.SanitizationError):
        MODULE.sanitize_report([finding(File=bad_file)])


@pytest.mark.parametrize("bad_line", [0, -1, True, "abc", None])
def test_sanitizer_rejects_invalid_line_metadata(bad_line):
    with pytest.raises(MODULE.SanitizationError):
        MODULE.sanitize_report([finding(StartLine=bad_line)])


def test_sanitizer_rejects_unknown_report_shape_and_invalid_rule_id():
    with pytest.raises(MODULE.SanitizationError):
        MODULE.sanitize_report({"not": "a list"})
    with pytest.raises(MODULE.SanitizationError):
        MODULE.sanitize_report([finding(RuleID="generic-api-key\nLEAK=1")])


def test_gitlab_job_keeps_original_scanner_blocking_and_summary_non_blocking():
    ci = CI_PATH.read_text(encoding="utf-8")
    original = ci.split("secret_detection_gitleaks:", 1)[1].split(
        "secret_detection_gitleaks_sanitized_summary:", 1
    )[0]
    summary = ci.split("secret_detection_gitleaks_sanitized_summary:", 1)[1].split(
        "backend_dependency_scanning_pip_audit:", 1
    )[0]

    assert "--redact" in original
    assert "--exit-code 1" in original
    assert "gitlab-secret-detection-report.json" in original
    assert "needs:" in summary
    assert "job: secret_detection_gitleaks" in summary
    assert "artifacts: true" in summary
    assert "when: always" in summary
    assert "allow_failure: true" in summary
    assert "sanitize_gitleaks_report.py" in summary
    assert "gitlab-secret-detection-summary.json" in summary
