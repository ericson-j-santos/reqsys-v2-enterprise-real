from scripts.build_credential_control_plane_dashboard import build_dashboard


def test_dashboard_never_claims_to_expose_secret_values():
    html = build_dashboard(
        {
            "contract": "reqsys-credential-control-plane-health",
            "schema_version": "1.0.0",
            "status": "EVIDENCE_INCOMPLETE",
            "summary": {
                "environments_total": 1,
                "bindings_total": 1,
                "available_bindings": 0,
                "missing_bindings": 0,
                "degraded_bindings": 0,
                "unknown_bindings": 1,
            },
            "environments": {
                "dev": {
                    "bindings": [
                        {
                            "credential_id": "jwt-dev",
                            "provider": "fly",
                            "reference": "JWT_SECRET",
                            "consumer": "reqsys-api-dev",
                            "status": "UNKNOWN",
                            "reason": "fly_state_missing",
                        }
                    ]
                }
            },
        }
    )

    assert "JWT_SECRET" in html
    assert "Valores de tokens, senhas e secrets não são exibidos" in html
    assert "secret_values_exposed=false" in html
