from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / ".github" / "workflows" / "teams-notification-dashboard.yml"
AVAILABILITY = ROOT / ".github" / "workflows" / "teams-dashboard-availability-monitor.yml"
DELIVERY = ROOT / ".github" / "workflows" / "teams-commit-notification.yml"
ISSUE_VALIDATOR = ROOT / "scripts" / "validate_issue_governance.py"


def _load_issue_validator():
    spec = importlib.util.spec_from_file_location("validate_issue_governance", ISSUE_VALIDATOR)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_delivery_slo_counts_only_real_delivery_events() -> None:
    text = DASHBOARD.read_text(encoding="utf-8")

    assert 'DELIVERY_EVENTS: "push,workflow_run"' in text
    assert 'allowed_events: set[str] | None = None' in text
    assert 'run.get("event") not in allowed_events' in text
    assert 'allowed_events=delivery_events' in text
    assert 'delivery_events != {"push", "workflow_run"}' in text

    # O watchdog deve continuar separado, nunca entrar silenciosamente no SLO.
    assert 'allowed_events={"schedule"}' in text
    assert '"delivery_event_filter": sorted(delivery_events)' in text
    assert '"locator_watch": {' in text
    assert '"recent_locator_watch_runs": [' in text


def test_locator_watch_remains_fail_closed() -> None:
    text = DELIVERY.read_text(encoding="utf-8")

    assert 'cron: "*/10 * * * *"' in text
    assert "watch-locator" in text
    assert "steps.locator.outputs.state != 'healthy'" in text
    assert "no_valid_fresh_signed_locator" in text
    assert "exit 1" in text
    assert "continue-on-error:" not in text


def test_availability_monitor_runs_after_successful_pages_deploy() -> None:
    text = AVAILABILITY.read_text(encoding="utf-8")

    trigger = text.split("permissions:", 1)[0]
    assert "workflow_run:" in trigger
    assert "- Deploy ReqSys Pages Composite" in trigger
    assert "types:" in trigger
    assert "- completed" in trigger
    assert "schedule:" in trigger
    assert "workflow_dispatch:" in trigger

    assert "github.event_name != 'workflow_run'" in text
    assert "github.event.workflow_run.conclusion == 'success'" in text


def test_operational_incident_is_governance_compliant_panel() -> None:
    text = AVAILABILITY.read_text(encoding="utf-8")
    assert "<!-- reqsys-operational-panel -->" in text
    assert 'gh issue edit "$existing"' in text

    validator = _load_issue_validator()
    body = """<!-- reqsys-operational-panel -->
## Dashboard GitHub → Teams indisponível

- Estado: unhealthy
"""
    result = validator.validate_issue(
        title="[INCIDENT][TEAMS] Dashboard de SLO indisponível",
        body=body,
        issue_number=3002,
        author_type="Bot",
    )
    assert result.valid is True
    assert result.scope == validator.SCOPE_OPERATIONAL_PANEL
    assert result.missing_fields == []


def test_availability_monitor_keeps_real_health_gate() -> None:
    text = AVAILABILITY.read_text(encoding="utf-8")

    assert 'MAX_DATA_AGE_HOURS: "48"' in text
    assert 'state = "healthy" if not errors else "unhealthy"' in text
    assert "data_age_hours" in text
    assert "freshness_errors" in text
    assert "Fechar incidente após recuperação" in text
    assert "Aplicar gate de disponibilidade" in text
    assert "steps.health.outputs.state != 'healthy'" in text
    assert "run: exit 1" in text
    assert "continue-on-error:" not in text
