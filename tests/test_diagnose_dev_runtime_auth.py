from pathlib import Path

import pytest

from scripts.diagnose_dev_runtime_auth import (
    build_targets,
    classify,
    sanitize_auth_payload,
)

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "dev-runtime-auth-diagnostics.yml"


def test_sanitize_auth_payload_remove_identificadores_sensiveis():
    payload = {
        "data": {
            "azure_enabled": False,
            "certificate_enabled": False,
            "demo_login_enabled": False,
            "environment": "development",
            "auth_status": "misconfigured",
            "missing_fields": ["AZURE_TENANT_ID", "AZURE_CLIENT_ID"],
            "expected_redirect_uri": "https://app-dev.example.net",
            "azure_tenant_id": "nao-deve-sair",
            "azure_client_id": "nao-deve-sair",
            "access_token": "nao-deve-sair",
        }
    }

    sanitized = sanitize_auth_payload(payload)

    assert sanitized["azure_enabled"] is False
    assert sanitized["missing_fields"] == ["AZURE_TENANT_ID", "AZURE_CLIENT_ID"]
    assert "azure_tenant_id" not in sanitized
    assert "azure_client_id" not in sanitized
    assert "access_token" not in sanitized


def test_classify_detecta_drift_runtime_quando_demo_declarado_mas_desabilitado():
    aggregate = {
        name: {
            "attempts": 10,
            "success_count": 10,
            "failure_count": 0,
        }
        for name in ("frontend", "health", "runtime_health", "readiness", "liveness")
    }
    auth = {
        "azure_enabled": False,
        "certificate_enabled": False,
        "demo_login_enabled": False,
        "missing_fields": ["AZURE_TENANT_ID", "AZURE_CLIENT_ID"],
    }
    static_state = {
        "backend": {
            "min_machines_running": 1,
            "allow_demo_login_declared": True,
            "public_environment_declared": "development",
        },
        "frontend": {"min_machines_running": 1},
    }

    result = classify(aggregate, auth, static_state)

    assert result["status"] == "degraded"
    assert result["operational_risk"] == "high"
    assert result["minimum_running_configuration_ok"] is True
    assert "cold_start_configuration_risk" not in result["suspected_causes"]
    assert "all_login_methods_disabled_at_runtime" in result["suspected_causes"]
    assert "runtime_configuration_drift_demo_login" in result["suspected_causes"]
    assert "azure_runtime_configuration_missing" in result["suspected_causes"]
    assert result["production_touched"] is False


def test_classify_ready_com_runtime_estavel_e_auth_disponivel():
    aggregate = {
        name: {
            "attempts": 10,
            "success_count": 10,
            "failure_count": 0,
        }
        for name in ("frontend", "health", "runtime_health", "readiness", "liveness")
    }
    auth = {
        "azure_enabled": True,
        "certificate_enabled": False,
        "demo_login_enabled": True,
        "missing_fields": [],
    }
    static_state = {
        "backend": {
            "min_machines_running": 1,
            "allow_demo_login_declared": True,
            "public_environment_declared": "development",
        },
        "frontend": {"min_machines_running": 1},
    }

    result = classify(aggregate, auth, static_state)

    assert result["status"] == "ready"
    assert result["operational_risk"] == "low"
    assert result["auth_available"] is True
    assert result["suspected_causes"] == []


def test_build_targets_requires_explicit_provider_neutral_https_urls():
    targets = build_targets(
        "https://app-dev.example.net",
        "https://api-dev.example.net",
    )

    assert targets["frontend"] == "https://app-dev.example.net/"
    assert targets["health"] == "https://api-dev.example.net/health"
    assert targets["auth_config"] == "https://api-dev.example.net/v1/auth/config"


def test_build_targets_rejects_fly_and_plain_http():
    with pytest.raises(ValueError, match="retirado definitivamente"):
        build_targets("https://legacy.fly.dev", "https://api.example.net")
    with pytest.raises(ValueError, match="HTTPS"):
        build_targets("https://app.example.net", "http://api.example.net")


def test_workflow_summary_does_not_fail_when_evidence_is_absent():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    summary_step = workflow.split("      - name: Publicar resumo sanitizado", 1)[1].split(
        "      - name: Upload da evidência sanitizada",
        1,
    )[0]

    guard = "if [[ -f /tmp/summary.md ]]; then"
    publish = 'cat /tmp/summary.md >> "$GITHUB_STEP_SUMMARY"'

    assert guard in summary_step
    assert publish in summary_step
    assert summary_step.index(guard) < summary_step.index(publish)
