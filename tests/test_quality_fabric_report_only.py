from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "quality-fabric-report-only.yml"
MATRIX = ROOT / "governance" / "testing" / "test-matrix.yaml"


def test_workflow_is_explicitly_non_blocking_and_uploads_artifacts():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "continue-on-error: true" in text
    assert "actions/upload-artifact@" in text
    assert "--profile pr_report" in text
    assert "differential_coverage.py" in text
    assert "--enforce" not in text


def test_pr_report_profile_uses_coverage_suite_once():
    payload = json.loads(MATRIX.read_text(encoding="utf-8"))
    suites = payload["profiles"]["pr_report"]["suites"]
    assert "backend_coverage_report" in suites
    assert "backend_tests" not in suites

    command = payload["suites"]["backend_coverage_report"]["command"]
    joined = " ".join(command)
    assert "--cov=app" in joined
    assert "backend-coverage.json" in joined


def test_quality_fabric_selftest_covers_increment_two_contracts():
    payload = json.loads(MATRIX.read_text(encoding="utf-8"))
    command = payload["suites"]["quality_fabric_selftest"]["command"]
    assert "tests/test_differential_coverage.py" in command
    assert "tests/test_quality_fabric_report_only.py" in command
