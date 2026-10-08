import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "reconcile_pc24x7_teams_flow_bot_owner.py"
SPEC = importlib.util.spec_from_file_location(
    "reconcile_pc24x7_teams_flow_bot_owner", SCRIPT
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_reconcile_creates_owner_and_returns_only_fingerprints(monkeypatch) -> None:
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs.get("payload")))
        if url.endswith("/auth/session"):
            return {"success": True, "data": {"papel": "admin"}}
        if url.endswith("/owners") and method == "GET":
            return {"success": True, "data": {"items": []}}
        if url.endswith("/owners") and method == "POST":
            return {"success": True, "data": {"id": 7}}
        if url.endswith("/status"):
            return {
                "success": True,
                "data": {
                    "rotas": [
                        {
                            "canal": "flow_bot",
                            "disponivel": True,
                            "donos_ativos": 1,
                        }
                    ]
                },
            }
        if url.endswith("/messages"):
            return {
                "success": True,
                "data": {
                    "entregue": True,
                    "status_code": 200,
                    "correlation_id": "delivery-1",
                },
            }
        raise AssertionError((method, url))

    monkeypatch.setattr(module, "_request_json", fake_request)
    result = module.reconcile(
        api_base="https://runtime.trycloudflare.com",
        admin_jwt="admin-secret",
        webhook_url="https://flow.example.com/secret-trigger",
        owner_email="owner@example.com",
        recipient="recipient@example.com",
        correlation_id="corr-1",
    )

    assert result["status"] == "ready"
    assert result["action"] == "created"
    assert result["delivery_confirmed"] is True
    serialized = str(result)
    assert "admin-secret" not in serialized
    assert "secret-trigger" not in serialized
    assert "owner@example.com" not in serialized
    assert any(method == "POST" and url.endswith("/owners") for method, url, _ in calls)


def test_reconcile_updates_matching_owner(monkeypatch) -> None:
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url))
        if url.endswith("/auth/session"):
            return {"success": True, "data": {"papel": "admin"}}
        if url.endswith("/owners") and method == "GET":
            return {
                "success": True,
                "data": {
                    "items": [
                        {
                            "id": 9,
                            "owner_email": "owner@example.com",
                            "ativo": True,
                        }
                    ]
                },
            }
        if url.endswith("/owners/9") and method == "PATCH":
            return {"success": True, "data": {"id": 9}}
        if url.endswith("/status"):
            return {
                "success": True,
                "data": {
                    "rotas": [
                        {
                            "canal": "flow_bot",
                            "disponivel": True,
                            "donos_ativos": 1,
                        }
                    ]
                },
            }
        if url.endswith("/messages"):
            return {"success": True, "data": {"entregue": True, "status_code": 200}}
        raise AssertionError((method, url))

    monkeypatch.setattr(module, "_request_json", fake_request)
    result = module.reconcile(
        api_base="https://runtime.trycloudflare.com",
        admin_jwt="admin-secret",
        webhook_url="https://flow.example.com/secret-trigger",
        owner_email="owner@example.com",
        recipient="recipient@example.com",
        correlation_id="corr-2",
    )

    assert result["action"] == "updated"
    assert (
        "PATCH",
        "https://runtime.trycloudflare.com/v1/teams-gateway/flow-bot/owners/9",
    ) in calls


def test_reconcile_refreshes_expired_admin_jwt_only_in_dev(monkeypatch) -> None:
    observed_tokens = []

    def fake_request(method, url, **kwargs):
        if url.endswith("/auth/session"):
            token = kwargs.get("admin_jwt")
            observed_tokens.append(token)
            if token == "expired-secret":
                raise module.ReconcileError("api_http_401:/v1/auth/session")
            return {"success": True, "data": {"papel": "admin"}}
        if url.endswith("/auth/config"):
            return {
                "success": True,
                "data": {
                    "environment": "desenvolvimento",
                    "demo_login_enabled": True,
                },
            }
        if url.endswith("/auth/login"):
            return {
                "success": True,
                "data": {
                    "access_token": "fresh-ephemeral-secret",
                    "usuario": {"papel": "admin"},
                },
            }
        if url.endswith("/owners") and method == "GET":
            return {"success": True, "data": {"items": []}}
        if url.endswith("/owners") and method == "POST":
            return {"success": True, "data": {"id": 11}}
        if url.endswith("/status"):
            return {
                "success": True,
                "data": {
                    "rotas": [
                        {
                            "canal": "flow_bot",
                            "disponivel": True,
                            "donos_ativos": 1,
                        }
                    ]
                },
            }
        if url.endswith("/messages"):
            return {"success": True, "data": {"entregue": True}}
        raise AssertionError((method, url))

    monkeypatch.setattr(module, "_request_json", fake_request)
    result = module.reconcile(
        api_base="https://runtime.trycloudflare.com",
        admin_jwt="expired-secret",
        webhook_url="https://flow.example.com/secret-trigger",
        owner_email="owner@example.com",
        recipient="recipient@example.com",
        correlation_id="corr-refresh",
    )

    assert result["admin_auth_source"] == "dev_demo_ephemeral"
    assert result["admin_jwt_refreshed"] is True
    assert observed_tokens == ["expired-secret", "fresh-ephemeral-secret"]
    assert "fresh-ephemeral-secret" not in str(result)


def test_admin_jwt_refresh_fails_closed_outside_dev(monkeypatch) -> None:
    def fake_request(method, url, **kwargs):
        if url.endswith("/auth/session"):
            raise module.ReconcileError("api_http_401:/v1/auth/session")
        if url.endswith("/auth/config"):
            return {
                "success": True,
                "data": {"environment": "producao", "demo_login_enabled": True},
            }
        raise AssertionError((method, url))

    monkeypatch.setattr(module, "_request_json", fake_request)
    with pytest.raises(module.ReconcileError, match="non_dev_environment"):
        module.reconcile(
            api_base="https://runtime.trycloudflare.com",
            admin_jwt="expired-secret",
            webhook_url="https://flow.example.com/secret-trigger",
            owner_email="owner@example.com",
            recipient="recipient@example.com",
            correlation_id="corr-prod",
        )


@pytest.mark.parametrize(
    "value",
    [
        "http://runtime.trycloudflare.com",
        "https://trycloudflare.com",
        "https://runtime.example.com",
        "https://user:pass@runtime.trycloudflare.com",
    ],
)
def test_api_base_is_fail_closed(value: str) -> None:
    with pytest.raises(module.ReconcileError, match="api_base_not_governed"):
        module._validate_api_base(value)


def test_workflow_uses_environment_secrets_without_cli_values() -> None:
    workflow_path = ROOT / ".github/workflows/teams-commit-notification.yml"
    workflow = workflow_path.read_text(encoding="utf-8")
    assert "reconcile-flow-bot:" in workflow
    assert "inputs.operation == 'reconcile-flow-bot'" in workflow
    assert "environment: development" in workflow
    assert "secrets.COFRE_ADMIN_JWT" in workflow
    assert "secrets.TEAMS_WEBHOOK_URL" in workflow
    assert "secrets.TEAMS_WEBHOOK_RECIPIENT" in workflow
    assert "--confirm RECONCILE-PC24X7-TEAMS-FLOW-BOT-DEV" in workflow
    assert "--admin-jwt" not in workflow
    assert "--webhook-url" not in workflow
