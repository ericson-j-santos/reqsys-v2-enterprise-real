from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "notify_reqsys_logs_teams.py"
SPEC = importlib.util.spec_from_file_location("notify_reqsys_logs_teams", MODULE_PATH)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def test_redact_text_masks_secrets_and_email() -> None:
    value = "Authorization: Bearer abc123 password=segredo user=ericson@example.com"
    sanitized = module.redact_text(value)
    assert "abc123" not in sanitized
    assert "segredo" not in sanitized
    assert "ericson@example.com" not in sanitized
    assert "[REDACTED]" in sanitized
    assert "[EMAIL_REDACTED]" in sanitized


def test_summarize_failed_jobs_ignores_success() -> None:
    jobs = [
        {"name": "lint", "conclusion": "success", "steps": []},
        {
            "name": "tests",
            "conclusion": "failure",
            "steps": [
                {"name": "Checkout", "conclusion": "success"},
                {"name": "Pytest", "conclusion": "failure"},
            ],
        },
    ]
    details = module.summarize_failed_jobs(jobs)
    assert "Job: tests — failure" in details
    assert "Etapa: Pytest — failure" in details
    assert all("lint" not in item for item in details)


def test_build_message_contains_governed_evidence() -> None:
    event = module.LogEvent(
        source="github-actions",
        environment="main",
        severity="critical",
        status="failure",
        summary="CI interrompido",
        details=("Job: tests — failure",),
        run_url="https://github.com/acme/repo/actions/runs/1",
        workflow="CI",
        run_id="1",
        correlation_id="reqsys-log-1",
    )
    message = module.build_message(event)
    assert "Correlation ID: reqsys-log-1" in message
    assert "Job: tests — failure" in message
    assert "logs brutos permanecem" in message
