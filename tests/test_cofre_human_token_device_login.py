import importlib.util
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path('scripts/cofre_human_token.py')
SCRIPT_DIR = str(SCRIPT.parent.resolve())
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
spec = importlib.util.spec_from_file_location('cofre_human_token', SCRIPT)
subject = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = subject
spec.loader.exec_module(subject)


def _sanitized_local_status(status="valid"):
    return {
        "schema_version": "1.0.0",
        "status": status,
        "environment": "dev",
        "vault_initialized": True,
        "credential_present": True,
        "credential_decryptable": True,
        "expires_at_utc": "2026-10-24T18:00:00Z",
        "remaining_minutes": 55,
        "human_action_required": status != "valid",
        "secret_value_exposed": False,
        "production_touched": False,
    }


def test_local_status_uses_fixed_dev_container_and_sanitized_contract(monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(_sanitized_local_status()) + "\n",
            stderr="",
        )

    monkeypatch.setattr(subject.subprocess, "run", fake_run)

    status = subject._local_status("dev", warning_minutes=20)

    assert status["status"] == "valid"
    assert status["secret_value_exposed"] is False
    assert status["production_touched"] is False
    assert captured["command"][0:2] == ["docker", "exec"]
    assert subject.DEFAULT_LOCAL_COFRE_CONTAINER in captured["command"]
    assert "COFRE_HUMAN_JWT_ENVIRONMENT=dev" in captured["command"]
    assert "COFRE_HUMAN_JWT_WARNING_MINUTES=20" in captured["command"]
    assert captured["kwargs"]["shell"] is False


@pytest.mark.parametrize(
    ("environment", "container", "message"),
    [
        ("stg", subject.DEFAULT_LOCAL_COFRE_CONTAINER, "somente em DEV"),
        ("dev", "outro-container", "não autorizado"),
    ],
)
def test_local_status_blocks_non_dev_or_noncanonical_container(
    monkeypatch, environment, container, message
):
    monkeypatch.setattr(
        subject.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("docker não deveria ser chamado"),
    )

    with pytest.raises(subject.CofreTokenError, match=message):
        subject._local_status(environment, container=container)


def test_local_status_command_writes_only_sanitized_evidence(monkeypatch, tmp_path, capsys):
    output = tmp_path / "status.json"
    monkeypatch.setattr(
        subject,
        "_local_status",
        lambda *_args, **_kwargs: _sanitized_local_status(),
    )
    args = SimpleNamespace(
        environment="dev",
        container=subject.DEFAULT_LOCAL_COFRE_CONTAINER,
        warning_minutes=15,
        output=str(output),
        require_valid=True,
    )

    subject.cmd_local_status(args)

    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert evidence == _sanitized_local_status()
    assert "token" not in output.read_text(encoding="utf-8").lower()
    stdout = capsys.readouterr().out
    assert "opaque-id-token" not in stdout
    assert "reqsys-secret-jwt" not in stdout


def test_local_status_require_valid_fails_closed_after_writing_evidence(monkeypatch, tmp_path):
    output = tmp_path / "status.json"
    monkeypatch.setattr(
        subject,
        "_local_status",
        lambda *_args, **_kwargs: _sanitized_local_status("expired"),
    )
    args = SimpleNamespace(
        environment="dev",
        container=subject.DEFAULT_LOCAL_COFRE_CONTAINER,
        warning_minutes=15,
        output=str(output),
        require_valid=True,
    )

    with pytest.raises(subject.CofreTokenError, match="não está válido: expired"):
        subject.cmd_local_status(args)

    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "expired"


def test_device_code_pending_then_returns_id_token(monkeypatch, capsys):
    responses = iter([
        (200, {
            "device_code": "opaque-device-code",
            "user_code": "ABCD-EFGH",
            "verification_uri": "https://microsoft.com/devicelogin",
            "expires_in": 900,
            "interval": 5,
        }),
        (400, {"error": "authorization_pending"}),
        (200, {"id_token": "opaque-id-token"}),
    ])
    monkeypatch.setattr(subject, "_http_form", lambda *_args, **_kwargs: next(responses))
    monkeypatch.setattr(subject.time, "sleep", lambda _seconds: None)

    assert subject._device_code_token("tenant", "client") == "opaque-id-token"
    output = capsys.readouterr().out
    assert "ABCD-EFGH" in output
    assert "opaque-device-code" not in output
    assert "opaque-id-token" not in output


def test_device_code_slow_down_increases_interval(monkeypatch):
    responses = iter([
        (200, {
            "device_code": "opaque",
            "user_code": "ABCD-EFGH",
            "expires_in": 900,
            "interval": 5,
        }),
        (400, {"error": "slow_down"}),
        (200, {"id_token": "id-token"}),
    ])
    sleeps = []
    monkeypatch.setattr(subject, "_http_form", lambda *_args, **_kwargs: next(responses))
    monkeypatch.setattr(subject.time, "sleep", sleeps.append)

    assert subject._device_code_token("tenant", "client") == "id-token"
    assert sleeps == [5, 10]


@pytest.mark.parametrize(
    ("error", "message"),
    [
        ("authorization_declined", "recusado"),
        ("expired_token", "expirou"),
    ],
)
def test_device_code_terminal_errors(monkeypatch, error, message):
    responses = iter([
        (200, {"device_code": "opaque", "user_code": "ABCD", "expires_in": 900}),
        (400, {"error": error}),
    ])
    monkeypatch.setattr(subject, "_http_form", lambda *_args, **_kwargs: next(responses))
    monkeypatch.setattr(subject.time, "sleep", lambda _seconds: None)

    with pytest.raises(subject.CofreTokenError, match=message):
        subject._device_code_token("tenant", "client")


def test_device_login_exchanges_and_stores_without_printing_tokens(monkeypatch, capsys):
    class Args:
        environment = "dev"
        base_url = "https://api-dev.example.net"

    monkeypatch.setattr(
        subject,
        "_azure_runtime_config",
        lambda _base: ("https://api-dev.example.net/api", "tenant", "client"),
    )
    monkeypatch.setattr(subject, "_device_code_token", lambda *_args: "azure-secret-id-token")

    def fake_request(method, url, *, headers, body=None):
        assert method == "POST"
        assert url == "https://api-dev.example.net/api/v1/auth/azure"
        assert body == {"id_token": "azure-secret-id-token"}
        return {"data": {"access_token": "reqsys-secret-jwt"}}

    stored = {}
    monkeypatch.setattr(subject, "_http_request", fake_request)
    monkeypatch.setattr(
        subject,
        "_set_token",
        lambda environment, base_url, token: stored.update(
            environment=environment, base_url=base_url, token=token
        ) or int(time.time()) + 3600,
    )

    subject.cmd_device_login(Args())

    assert stored == {
        "environment": "dev",
        "base_url": "https://api-dev.example.net/api",
        "token": "reqsys-secret-jwt",
    }
    output = capsys.readouterr().out
    assert "azure-secret-id-token" not in output
    assert "reqsys-secret-jwt" not in output
    assert "Nenhum token foi exibido" in output


def test_runtime_config_discovers_public_api_prefix(monkeypatch):
    calls = []

    def fake_request(method, url, *, headers, body=None):
        calls.append(url)
        if url == "https://runtime.example.net/v1/auth/config":
            raise subject.CofreTokenError("Resposta não JSON")
        return {
            "data": {
                "azure_enabled": True,
                "azure_tenant_id": "tenant",
                "azure_client_id": "client",
            }
        }

    monkeypatch.setattr(subject, "_http_request", fake_request)

    assert subject._azure_runtime_config("https://runtime.example.net") == (
        "https://runtime.example.net/api",
        "tenant",
        "client",
    )
    assert calls == [
        "https://runtime.example.net/v1/auth/config",
        "https://runtime.example.net/api/v1/auth/config",
    ]


def test_gateway_retry_preserves_operation_until_recovery(monkeypatch, capsys):
    outcomes = iter([
        subject.CofreTokenError("HTTP 502 em POST"),
        subject.CofreTokenError("HTTP 503 em POST"),
        {"data": {"access_token": "opaque"}},
    ])
    sleeps = []

    def operation():
        outcome = next(outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(subject.time, "sleep", sleeps.append)

    assert subject._retry_gateway(operation, attempts=3)["data"]["access_token"] == "opaque"
    assert sleeps == [5, 5]
    assert "aguardando recuperação" in capsys.readouterr().out


def test_gateway_retry_fails_fast_for_non_transient_error(monkeypatch):
    monkeypatch.setattr(subject.time, "sleep", lambda _seconds: pytest.fail("não deveria aguardar"))

    with pytest.raises(subject.CofreTokenError, match="HTTP 401"):
        subject._retry_gateway(
            lambda: (_ for _ in ()).throw(subject.CofreTokenError("HTTP 401 em POST")),
            attempts=3,
        )


def test_msal_cache_renews_without_printing_secret(monkeypatch, tmp_path, capsys):
    state = tmp_path / "msal.json"
    state.write_text(json.dumps({
        "sessionStorage": [{
            "name": "msal.refresh",
            "value": json.dumps({
                "credentialType": "RefreshToken",
                "clientId": "client-id",
                "secret": "refresh-secret",
            }),
        }],
    }), encoding="utf-8")

    def fake_form(url, body):
        assert url.endswith("/tenant-id/oauth2/v2.0/token")
        assert body["refresh_token"] == "refresh-secret"
        return 200, {"id_token": "renewed-id-token"}

    monkeypatch.setattr(subject, "_http_form", fake_form)

    assert subject._msal_cached_id_token(state, "tenant-id", "client-id") == "renewed-id-token"
    assert "refresh-secret" not in capsys.readouterr().out


def test_msal_cache_requires_matching_client(monkeypatch, tmp_path):
    state = tmp_path / "msal.json"
    state.write_text(json.dumps({
        "sessionStorage": [{
            "value": json.dumps({
                "credentialType": "RefreshToken",
                "clientId": "other-client",
                "secret": "secret",
            }),
        }],
    }), encoding="utf-8")
    monkeypatch.setattr(subject, "_http_form", lambda *_args: pytest.fail("não deveria chamar rede"))

    with pytest.raises(subject.CofreTokenError, match="não contém refresh token"):
        subject._msal_cached_id_token(state, "tenant-id", "client-id")


def test_msal_cache_ignores_non_object_entries(monkeypatch, tmp_path):
    state = tmp_path / "msal.json"
    state.write_text(json.dumps({
        "sessionStorage": [
            {"value": json.dumps(["metadata"])},
            {"value": json.dumps({
                "credentialType": "RefreshToken",
                "clientId": "client-id",
                "secret": "refresh-secret",
            })},
        ],
    }), encoding="utf-8")
    monkeypatch.setattr(subject, "_http_form", lambda *_args: (200, {"id_token": "id-token"}))

    assert subject._msal_cached_id_token(state, "tenant-id", "client-id") == "id-token"
