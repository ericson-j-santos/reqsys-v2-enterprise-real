from scripts.project_credential_control_plane_health import build_health_report


def _catalog():
    return {
        "providers": {"fly": {}, "github": {}, "azure": {}},
        "credentials": [
            {
                "credential_id": "jwt-dev",
                "kind": "SECRET",
                "provider": "fly",
                "secret_reference": "JWT_SECRET",
            },
            {
                "credential_id": "github-api",
                "kind": "SECRET",
                "provider": "github",
                "secret_reference": "REQSYS_API_TOKEN",
            },
        ],
        "bindings": [
            {
                "credential_id": "jwt-dev",
                "environment": "dev",
                "consumer": "reqsys-api-dev",
            },
            {
                "credential_id": "github-api",
                "environment": "dev",
                "consumer": "reqsys-api-dev",
            },
        ],
    }


def _envs():
    return {
        "canonical_environments": ["dev"],
        "environments": {
            "dev": {
                "api_app": "reqsys-api-dev",
                "frontend_app": "reqsys-app-dev",
            }
        },
    }


def test_health_is_healthy_with_sanitized_provider_evidence():
    report = build_health_report(
        _catalog(),
        _envs(),
        fly_states={
            "dev": {
                "environment": "dev",
                "secret_values_persisted": False,
                "api": {
                    "commands": {"secrets": {"ok": True}},
                    "secrets": [
                        {"name": "JWT_SECRET", "deployment_status": "deployed"}
                    ],
                },
            }
        },
        provider_observations={
            ("github", "dev"): {
                "provider": "github",
                "environment": "dev",
                "ok": True,
                "secret_values_exposed": False,
                "references": [{"name": "REQSYS_API_TOKEN", "status": "present"}],
            }
        },
        generated_at_epoch=123,
    )

    assert report["status"] == "HEALTHY"
    assert report["summary"]["available_bindings"] == 2
    assert report["security"]["secret_values_exposed"] is False
    assert report["generated_at_epoch"] == 123


def test_health_fails_closed_when_reference_is_missing():
    report = build_health_report(
        _catalog(),
        _envs(),
        fly_states={
            "dev": {
                "environment": "dev",
                "secret_values_persisted": False,
                "api": {
                    "commands": {"secrets": {"ok": True}},
                    "secrets": [],
                },
            }
        },
        generated_at_epoch=123,
    )

    assert report["status"] == "DEGRADED"
    assert report["summary"]["missing_bindings"] == 1
    assert report["summary"]["unknown_bindings"] == 1
    assert any("required_reference_missing" in item for item in report["risks"])
