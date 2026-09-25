from __future__ import annotations

from scripts.probe_copilot_cloud_agent_metadata import (
    CLOUD_CONFIG_PATH,
    VARIABLE_NAME,
    VARIABLE_PATH,
    sanitize_cloud_configuration,
    sanitize_variable,
)


def test_probe_never_targets_agents_credential_endpoint() -> None:
    joined = f"{CLOUD_CONFIG_PATH} {VARIABLE_PATH}".lower()
    assert "agents/secrets" not in joined
    assert "agents/secret" not in joined


def test_variable_evidence_never_persists_value() -> None:
    raw = {
        "name": VARIABLE_NAME,
        "value": "https://example.invalid/mcp",
        "created_at": "2026-09-25T00:00:00Z",
        "updated_at": "2026-09-25T00:01:00Z",
    }
    sanitized = sanitize_variable(raw)

    assert sanitized["exists"] is True
    assert sanitized["value_present"] is True
    assert "value" not in sanitized
    assert "https://example.invalid/mcp" not in repr(sanitized)


def test_cloud_configuration_keeps_only_bounded_metadata() -> None:
    raw = {
        "mcp_configuration": {"servers": {"private": {"headers": {"Authorization": "masked"}}}},
        "enabled_tools": {
            "codeql": True,
            "copilot_code_review": False,
        },
        "require_actions_workflow_approval": True,
        "is_firewall_enabled": True,
        "is_firewall_recommended_allowlist_enabled": False,
        "is_automations_enabled": True,
        "require_write_access_for_automation_triggers": True,
        "unexpected_nested_payload": {"do_not_persist": "x"},
    }

    sanitized = sanitize_cloud_configuration(raw)

    assert sanitized["mcp_configuration_present"] is True
    assert sanitized["enabled_tools"] == ["codeql"]
    assert sanitized["disabled_tools"] == ["copilot_code_review"]
    assert sanitized["require_actions_workflow_approval"] is True
    assert "servers" not in repr(sanitized)
    assert "do_not_persist" not in repr(sanitized)
