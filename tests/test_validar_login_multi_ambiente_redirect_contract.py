from __future__ import annotations

from scripts import validar_login_multi_ambiente as login_validator


def _base_config() -> dict[str, str]:
    return {
        "api_url": "https://api.dev.example",
        "frontend_url": "https://app.dev.example",
        "app_env": "development",
    }


def test_downgrade_redirect_metadata_drift_preserves_other_errors() -> None:
    result = {
        "success": False,
        "errors": [
            "expected_redirect_uri divergente: esperado=https://app.dev.example atual=https://app.dev.example/auth/callback.html",
            "azure_client_id público está ausente",
        ],
        "warnings": [],
        "data": {},
    }

    normalized = login_validator._downgrade_redirect_metadata_drift(result)

    assert normalized["success"] is False
    assert normalized["errors"] == ["azure_client_id público está ausente"]
    assert normalized["data"]["redirect_contract_status"] == "api_metadata_drift"
    assert "bundle público validado" in normalized["warnings"][0]


def test_public_bundle_success_makes_api_redirect_drift_non_blocking(monkeypatch) -> None:
    monkeypatch.setattr(
        login_validator,
        "validar_config",
        lambda *_args, **_kwargs: {
            "success": False,
            "errors": [
                "expected_redirect_uri divergente: esperado=https://app.dev.example atual=https://app.dev.example/auth/callback.html"
            ],
            "warnings": [],
            "data": {"demo_login_enabled": False},
        },
    )
    monkeypatch.setattr(
        login_validator,
        "validate_public_frontend",
        lambda *_args, **_kwargs: {"success": True, "errors": [], "scanned_files": ["bundle.js"]},
    )
    monkeypatch.setattr(
        login_validator,
        "_probe_demo_login",
        lambda *_args, **_kwargs: login_validator.LoginProbeResult(
            name="demo_login",
            ok=True,
            status_code=403,
        ),
    )

    result = login_validator.validate_environment_login("dev", _base_config(), timeout=1)

    assert result["login_ready"] is True
    assert result["operational_status"] == "ready"
    assert result["errors"] == []
    assert result["checks"]["azure_config"]["data"]["redirect_contract_status"] == "api_metadata_drift"


def test_redirect_drift_remains_blocking_when_public_bundle_is_invalid(monkeypatch) -> None:
    redirect_error = (
        "expected_redirect_uri divergente: esperado=https://app.dev.example "
        "atual=https://app.dev.example/auth/callback.html"
    )
    monkeypatch.setattr(
        login_validator,
        "validar_config",
        lambda *_args, **_kwargs: {
            "success": False,
            "errors": [redirect_error],
            "warnings": [],
            "data": {"demo_login_enabled": False},
        },
    )
    monkeypatch.setattr(
        login_validator,
        "validate_public_frontend",
        lambda *_args, **_kwargs: {
            "success": False,
            "errors": ["bundle contém /auth/callback.html"],
        },
    )
    monkeypatch.setattr(
        login_validator,
        "_probe_demo_login",
        lambda *_args, **_kwargs: login_validator.LoginProbeResult(
            name="demo_login",
            ok=True,
            status_code=403,
        ),
    )

    result = login_validator.validate_environment_login("dev", _base_config(), timeout=1)

    assert result["login_ready"] is False
    assert redirect_error in result["errors"]
    assert "bundle contém /auth/callback.html" in result["errors"]
