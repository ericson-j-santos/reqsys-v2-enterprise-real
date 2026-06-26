from scripts.validate_public_runtime import EndpointResult, build_payload


def _result(endpoint, ok=True, status_code=200, elapsed_ms=100, **extra):
    content_type = extra.pop("content_type", "application/json")
    return EndpointResult(
        endpoint=endpoint,
        url=f"https://reqsys.example.com{endpoint}",
        ok=ok,
        status_code=status_code,
        elapsed_ms=elapsed_ms,
        content_type=content_type,
        **extra,
    )


def test_build_payload_consolida_readiness_operacional_healthy():
    results = [
        _result("/health", cors_allow_origin="https://reqsys.example.com"),
        _result("/api/runtime/health"),
        _result("/api/runtime/readiness"),
        _result("/api/runtime/liveness"),
        _result("/", content_type="text/html", has_asset_reference=True, has_login_marker=True),
        _result("/runtime", content_type="text/html", has_runtime_dashboard_marker=True),
        _result("/api/runtime/dashboard", has_incident_marker=True),
    ]

    payload = build_payload(
        "https://reqsys.example.com",
        "prod",
        results,
        ("/health", "/api/runtime/health", "/api/runtime/readiness", "/api/runtime/liveness"),
        True,
    )

    assert payload["schema_version"] == "1.3.0"
    assert payload["checks"]["frontend_loading"] is True
    assert payload["checks"]["assets"] is True
    assert payload["checks"]["cors_basic"] is True
    assert payload["checks"]["incident_timeline"] is True
    assert payload["readiness"]["environment"] == "prod"
    assert payload["readiness"]["operational_status"] == "healthy"
    assert payload["readiness"]["readiness_percent"] == 100
    assert payload["readiness"]["dashboard_ready"] is True
    assert payload["readiness"]["login_ready"] is True


def test_build_payload_classifica_indisponivel_quando_required_falha():
    results = [
        _result("/health", ok=False, status_code=None),
        _result("/api/runtime/health", ok=False, status_code=503),
    ]

    payload = build_payload("https://reqsys.example.com", "staging", results, ("/health", "/api/runtime/health"), False)

    assert payload["readiness"]["operational_status"] == "unavailable"
    assert payload["readiness"]["reachable"] is False
    assert payload["readiness"]["blocking_issues"]
