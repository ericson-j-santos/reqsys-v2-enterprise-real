from __future__ import annotations

import base64
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path("scripts/planner_teams_delegated_session_store.py")
SPEC = importlib.util.spec_from_file_location("planner_teams_delegated_session_store", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _bundle(client_id: str = "client-1", secret: str = "refresh-secret") -> dict:
    return {
        "cookies": [{"name": "sid", "value": "cookie-secret"}],
        "sessionStorage": [
            {
                "name": "msal.refreshtoken",
                "value": json.dumps(
                    {
                        "credentialType": "RefreshToken",
                        "clientId": client_id,
                        "secret": secret,
                        "expiresOn": "1999999999",
                    }
                ),
            },
            {
                "name": "msal.accesstoken",
                "value": json.dumps(
                    {
                        "credentialType": "AccessToken",
                        "clientId": client_id,
                        "secret": "access-secret",
                    }
                ),
            },
        ],
    }


class FakeRunner:
    def __init__(self, *, client_id: str | None = None, session: dict | None = None):
        self.client_id = client_id
        self.session = session
        self.calls: list[list[str]] = []
        self.persisted: dict | None = None

    def run(self, args: list[str], *, check: bool = True):
        self.calls.append(list(args))
        if args[:3] == ["keyvault", "secret", "show"]:
            if self.client_id is None:
                return subprocess.CompletedProcess(args, 3, "", "SecretNotFound")
            return subprocess.CompletedProcess(args, 0, self.client_id + "\n", "")
        if args[:3] == ["keyvault", "secret", "download"]:
            if self.session is None:
                return subprocess.CompletedProcess(args, 3, "", "SecretNotFound")
            target = Path(args[args.index("--file") + 1])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(self.session), encoding="utf-8")
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[:3] == ["keyvault", "secret", "set"]:
            source = Path(args[args.index("--file") + 1])
            self.persisted = json.loads(source.read_text(encoding="utf-8"))
            return subprocess.CompletedProcess(args, 0, "", "")
        raise AssertionError(f"unexpected command: {args}")


def test_compact_state_keeps_only_one_refresh_token() -> None:
    compact = MODULE.compact_state(_bundle())
    raw = json.dumps(compact)
    assert "refresh-secret" in raw
    assert "access-secret" not in raw
    assert "cookie-secret" not in raw
    assert "cookies" not in compact
    assert len(compact["sessionStorage"]) == 1


def test_compact_state_rejects_wrong_dedicated_client() -> None:
    with pytest.raises(MODULE.SessionStoreError, match="msal_client_id_diverge"):
        MODULE.compact_state(_bundle("legacy-client"), expected_client_id="dedicated-client")


def test_load_bootstraps_dedicated_identity_when_session_missing(tmp_path: Path) -> None:
    runner = FakeRunner(client_id="dedicated-client", session=None)
    store = MODULE.KeyVaultSessionStore("kv-test", runner=runner)
    state = tmp_path / "state.json"

    result = MODULE.load_state(
        store,
        state_path=state,
        session_secret_name=MODULE.DEFAULT_SESSION_SECRET,
        client_id_secret_name=MODULE.DEFAULT_CLIENT_ID_SECRET,
    )

    assert result["source"] == "dedicated_identity_bootstrap"
    assert result["client_id"] == "dedicated-client"
    assert result["dedicated_identity_present"] is True
    assert json.loads(state.read_text(encoding="utf-8"))["sessionStorage"] == []


def test_load_uses_legacy_only_while_dedicated_identity_absent(tmp_path: Path) -> None:
    runner = FakeRunner(client_id=None, session=None)
    store = MODULE.KeyVaultSessionStore("kv-test", runner=runner)
    state = tmp_path / "state.json"
    legacy = base64.b64encode(json.dumps(_bundle("legacy-client")).encode()).decode()

    result = MODULE.load_state(
        store,
        state_path=state,
        session_secret_name=MODULE.DEFAULT_SESSION_SECRET,
        client_id_secret_name=MODULE.DEFAULT_CLIENT_ID_SECRET,
        legacy_b64=legacy,
    )

    assert result["source"] == "legacy_github_secret_fallback"
    assert result["client_id"] == "legacy-client"
    assert result["dedicated_identity_present"] is False


def test_load_discards_legacy_session_after_dedicated_cutover(tmp_path: Path) -> None:
    runner = FakeRunner(client_id="dedicated-client", session=_bundle("legacy-client"))
    store = MODULE.KeyVaultSessionStore("kv-test", runner=runner)
    state = tmp_path / "state.json"

    result = MODULE.load_state(
        store,
        state_path=state,
        session_secret_name=MODULE.DEFAULT_SESSION_SECRET,
        client_id_secret_name=MODULE.DEFAULT_CLIENT_ID_SECRET,
    )

    assert result["source"] == "dedicated_identity_cutover"
    assert result["client_id"] == "dedicated-client"
    assert json.loads(state.read_text(encoding="utf-8"))["sessionStorage"] == []


def test_persist_uses_file_and_never_secret_on_command_line(tmp_path: Path) -> None:
    runner = FakeRunner(client_id="dedicated-client")
    store = MODULE.KeyVaultSessionStore("kv-test", runner=runner)
    state = tmp_path / "state.json"
    state.write_text(json.dumps(_bundle("dedicated-client", "never-on-cli")), encoding="utf-8")

    result = MODULE.persist_state(
        store,
        state_path=state,
        session_secret_name=MODULE.DEFAULT_SESSION_SECRET,
        client_id_secret_name=MODULE.DEFAULT_CLIENT_ID_SECRET,
    )

    assert result["identity"] == "dedicated"
    assert result["secret_value_exposed"] is False
    assert runner.persisted is not None
    assert "never-on-cli" in json.dumps(runner.persisted)
    set_call = next(call for call in runner.calls if call[:3] == ["keyvault", "secret", "set"])
    assert "--file" in set_call
    assert "--value" not in set_call
    assert "never-on-cli" not in " ".join(set_call)
