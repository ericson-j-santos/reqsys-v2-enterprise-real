from scripts.diagnose_dev_runtime_auth import classify, sanitize_auth_payload


def test_sanitize_auth_payload_remove_identificadores_sensiveis():
    payload = {
        "data": {
            "azure_enabled": False,
            "certificate_enabled": False,
            "demo_login_enabled": False,
            "environment": "development",
            "auth_status": "misconfigured",
            "missing_fields": ["AZURE_TENANT_ID", "AZURE_CLIENT_ID"],
            "expected_redirect_uri": "https://reqsys-app-dev.fly.dev",
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
