from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "notify_reqsys_logs_teams.py"
SPEC = importlib.util.spec_from_file_location("notify_reqsys_logs_teams", MODULE_PATH)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def _event(**overrides):
    values = {
        "source": "github-actions",
        "environment": "main",
        "severity": "critical",
        "status": "failure",
        "summary": "CI interrompido",
        "details": ("Job: tests — failure",),
        "run_url": "https://github.com/acme/repo/actions/runs/1",
        "workflow": "CI",
        "run_id": "1",
        "correlation_id": "reqsys-log-1",
    }
    values.update(overrides)
    return module.LogEvent(**values)


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
    message = module.build_message(_event())
    assert "Correlation ID: reqsys-log-1" in message
    assert "Job: tests — failure" in message
    assert "logs brutos permanecem" in message


def test_sanitize_for_evidence_masks_destination_and_nested_secret() -> None:
    payload = {
        "entregue": True,
        "destination_id": "user@example.com",
        "provider_response": {"token": "token=abc123", "status": "ok"},
    }
    sanitized = module.sanitize_for_evidence(payload)
    assert sanitized["destination_id"] == "[REDACTED]"
    assert "abc123" not in str(sanitized)
    assert sanitized["provider_response"]["status"] == "ok"


def test_build_adaptive_card_has_structured_layout_and_action() -> None:
    card = module.build_adaptive_card(_event(severity="warning", status="cancelled"))
    assert card["type"] == "AdaptiveCard"
    assert card["version"] == "1.2"
    assert card["msteams"]["width"] == "Full"
    assert card["body"][0]["items"][0]["text"] == "ReqSys · Alerta operacional"
    assert card["body"][0]["items"][1]["text"] == "ATENÇÃO · main"
    fact_set = next(item for item in card["body"] if item["type"] == "FactSet")
    facts = {item["title"]: item["value"] for item in fact_set["facts"]}
    assert facts["Status"] == "Cancelado"
    assert facts["Workflow"] == "CI"
    assert card["actions"][0]["url"].endswith("/actions/runs/1")


def test_build_adaptive_card_limits_details() -> None:
    details = tuple(f"Job: item {index} — cancelled" for index in range(12))
    card = module.build_adaptive_card(_event(details=details))
    attention = next(
        item for item in card["body"]
        if item["type"] == "Container" and item.get("style") == "attention"
    )
    bullets = [item for item in attention["items"] if item.get("text", "").startswith("• ")]
    assert len(bullets) == 8
    assert attention["items"][-1]["text"] == "+ 4 item(ns) adicional(is) no GitHub Actions"


def test_build_adaptive_card_rejects_non_github_action_url() -> None:
    card = module.build_adaptive_card(_event(run_url="https://example.com/run/1"))
    assert "actions" not in card


def test_send_adaptive_webhook_dry_run_exposes_contract() -> None:
    event = _event()
    card = module.build_adaptive_card(event)
    result = module._send_adaptive_webhook(
        webhook_url="https://example.invalid/flow",
        recipient="user@example.com",
        title="ReqSys",
        message=module.build_message(event),
        adaptive_card=card,
        correlation_id=event.correlation_id,
        timeout=1.0,
        dry_run=True,
    )
    assert result["dry_run"] is True
    assert result["canal_usado"] == "flow_bot_adaptive_direct"
    assert result["provider_response"]["render_mode"] == "adaptive-card"


def test_write_evidence_does_not_persist_card_body(tmp_path: Path) -> None:
    event = _event()
    message = module.build_message(event)
    card = module.build_adaptive_card(event)
    path = tmp_path / "evidence.json"
    module._write_evidence(
        str(path),
        event=event,
        message=message,
        adaptive_card=card,
        delivery={"entregue": True, "to": "user@example.com"},
    )
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["render_mode"] == "adaptive-card"
    assert document["adaptive_card_version"] == "1.2"
    assert "adaptive_card_sha256" in document
    assert "body" not in document
    assert document["delivery"]["to"] == "[REDACTED]"
