#!/usr/bin/env python3
"""Sessão Microsoft delegada do Planner→Teams persistida no Azure Key Vault.

O valor persistido é um bundle mínimo contendo somente um RefreshToken MSAL.
Cookies, access tokens, id tokens, device_code e demais dados de navegador são
descartados. O script nunca imprime o valor do segredo.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_SESSION_SECRET = "reqsys-planner-teams-delegated-session-dev"
DEFAULT_CLIENT_ID_SECRET = "reqsys-planner-teams-delegated-client-id-dev"


class SessionStoreError(RuntimeError):
    pass


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class CommandRunner:
    def __init__(self) -> None:
        self.az = next((p for name in ("az", "az.cmd", "az.exe") if (p := shutil.which(name))), None)
        if not self.az:
            raise SessionStoreError("azure_cli_ausente")

    def run(self, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
        cp = subprocess.run([self.az, *args], text=True, capture_output=True, check=False, encoding="utf-8")
        if check and cp.returncode:
            detail = (cp.stderr or cp.stdout or "azure_cli_failed").strip()
            raise SessionStoreError(detail[:800])
        return cp


def _parse_refresh_entry(entry: dict[str, Any]) -> dict[str, Any] | None:
    raw = entry.get("value")
    if raw in (None, ""):
        return None
    try:
        item = json.loads(str(raw))
    except json.JSONDecodeError:
        return None
    if not isinstance(item, dict):
        return None
    kind = str(item.get("credentialType") or "").lower()
    name = str(entry.get("name") or "").lower()
    if kind != "refreshtoken" and "refreshtoken" not in name:
        return None
    client_id = str(item.get("clientId") or "").strip()
    secret = str(item.get("secret") or "")
    if not client_id or not secret:
        return None
    return {"entry_name": str(entry.get("name") or "msal.refreshtoken"), "client_id": client_id, "item": item}


def find_refresh(bundle: dict[str, Any]) -> dict[str, Any] | None:
    found = []
    for entry in bundle.get("sessionStorage") or []:
        if isinstance(entry, dict):
            parsed = _parse_refresh_entry(entry)
            if parsed:
                found.append(parsed)
    if not found:
        return None
    by_client = {item["client_id"]: item for item in found}
    if len(by_client) != 1:
        raise SessionStoreError(f"msal_refresh_token_ambiguo:{len(by_client)}")
    return next(iter(by_client.values()))


def compact_state(bundle: dict[str, Any], *, expected_client_id: str | None = None) -> dict[str, Any]:
    refresh = find_refresh(bundle)
    if refresh is None:
        raise SessionStoreError("msal_refresh_token_ausente")
    client_id = refresh["client_id"]
    if expected_client_id and client_id.lower() != expected_client_id.lower():
        raise SessionStoreError("msal_client_id_diverge_identidade_dedicada")
    original = refresh["item"]
    item = {
        "credentialType": "RefreshToken",
        "clientId": client_id,
        "secret": original["secret"],
    }
    if original.get("expiresOn") not in (None, ""):
        item["expiresOn"] = original["expiresOn"]
    return {
        "schemaVersion": 1,
        "authSource": "device_code_keyvault",
        "persistedAt": _iso_now(),
        "sessionStorage": [
            {
                "name": f"device-code-refreshtoken-{client_id}",
                "value": json.dumps(item, separators=(",", ":")),
            }
        ],
    }


def _minimal_state() -> dict[str, Any]:
    return {"schemaVersion": 1, "authSource": "key_vault_bootstrap", "sessionStorage": []}


def _is_not_found(cp: subprocess.CompletedProcess[str]) -> bool:
    text = f"{cp.stderr or ''} {cp.stdout or ''}".lower()
    return cp.returncode != 0 and (
        "secretnotfound" in text
        or "secret not found" in text
        or "(404)" in text
        or "status code: 404" in text
    )


class KeyVaultSessionStore:
    def __init__(self, vault_name: str, runner: CommandRunner | None = None) -> None:
        if not vault_name.strip():
            raise SessionStoreError("key_vault_name_ausente")
        self.vault_name = vault_name.strip()
        self.runner = runner or CommandRunner()

    def read_client_id(self, name: str) -> str | None:
        cp = self.runner.run(
            [
                "keyvault", "secret", "show",
                "--vault-name", self.vault_name,
                "--name", name,
                "--query", "value",
                "--output", "tsv",
                "--only-show-errors",
            ],
            check=False,
        )
        if _is_not_found(cp):
            return None
        if cp.returncode:
            raise SessionStoreError("key_vault_client_id_read_failed")
        value = (cp.stdout or "").strip()
        return value or None

    def download_session(self, name: str, target: Path) -> bool:
        target.parent.mkdir(parents=True, exist_ok=True)
        cp = self.runner.run(
            [
                "keyvault", "secret", "download",
                "--vault-name", self.vault_name,
                "--name", name,
                "--file", str(target),
                "--encoding", "utf-8",
                "--overwrite",
                "--only-show-errors",
            ],
            check=False,
        )
        if _is_not_found(cp):
            return False
        if cp.returncode:
            raise SessionStoreError("key_vault_session_download_failed")
        try:
            os.chmod(target, 0o600)
        except OSError:
            pass
        return True

    def persist_session(self, name: str, payload: dict[str, Any], *, identity_kind: str) -> None:
        fd, temp_name = tempfile.mkstemp(prefix="reqsys-msal-", suffix=".json")
        temp = Path(temp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
                handle.write("\n")
            try:
                os.chmod(temp, 0o600)
            except OSError:
                pass
            self.runner.run(
                [
                    "keyvault", "secret", "set",
                    "--vault-name", self.vault_name,
                    "--name", name,
                    "--file", str(temp),
                    "--encoding", "utf-8",
                    "--content-type", "application/json",
                    "--tags",
                    "credential_id=planner-teams-delegated-session-dev",
                    "environment=dev",
                    "component=planner-teams",
                    f"identity={identity_kind}",
                    "managed-by=reqsys",
                    "--output", "none",
                    "--only-show-errors",
                ]
            )
        finally:
            temp.unlink(missing_ok=True)


def _write_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SessionStoreError("msal_storage_state_invalido") from exc
    if not isinstance(data, dict):
        raise SessionStoreError("msal_storage_state_invalido")
    return data


def load_state(
    store: KeyVaultSessionStore,
    *,
    state_path: Path,
    session_secret_name: str,
    client_id_secret_name: str,
    legacy_b64: str = "",
) -> dict[str, Any]:
    dedicated_client_id = store.read_client_id(client_id_secret_name)
    restored = store.download_session(session_secret_name, state_path)
    source = "key_vault"
    client_id = dedicated_client_id

    if restored:
        bundle = _load_json(state_path)
        refresh = find_refresh(bundle)
        if refresh and dedicated_client_id and refresh["client_id"].lower() != dedicated_client_id.lower():
            restored = False
            source = "dedicated_identity_cutover"
        elif refresh:
            client_id = dedicated_client_id or refresh["client_id"]
        else:
            restored = False

    if not restored:
        if dedicated_client_id:
            _write_state(state_path, _minimal_state())
            client_id = dedicated_client_id
            if source != "dedicated_identity_cutover":
                source = "dedicated_identity_bootstrap"
        elif legacy_b64.strip():
            try:
                raw = base64.b64decode(legacy_b64, validate=True)
                bundle = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise SessionStoreError("legacy_msal_state_invalido") from exc
            if not isinstance(bundle, dict):
                raise SessionStoreError("legacy_msal_state_invalido")
            refresh = find_refresh(bundle)
            if refresh is None:
                raise SessionStoreError("legacy_msal_refresh_token_ausente")
            _write_state(state_path, bundle)
            client_id = refresh["client_id"]
            source = "legacy_github_secret_fallback"
        else:
            raise SessionStoreError("PLANNER_TEAMS_DELEGATED_IDENTITY_BOOTSTRAP_REQUIRED")

    if not client_id:
        raise SessionStoreError("msal_bootstrap_client_id_ausente")

    return {
        "status": "loaded",
        "source": source,
        "client_id": client_id,
        "dedicated_identity_present": bool(dedicated_client_id),
        "session_secret_present": restored,
        "secret_value_exposed": False,
    }


def persist_state(
    store: KeyVaultSessionStore,
    *,
    state_path: Path,
    session_secret_name: str,
    client_id_secret_name: str,
) -> dict[str, Any]:
    dedicated_client_id = store.read_client_id(client_id_secret_name)
    bundle = _load_json(state_path)
    compact = compact_state(bundle, expected_client_id=dedicated_client_id)
    refresh = find_refresh(compact)
    assert refresh is not None
    identity_kind = "dedicated" if dedicated_client_id else "legacy-migration"
    store.persist_session(session_secret_name, compact, identity_kind=identity_kind)
    return {
        "status": "persisted",
        "source": "azure_key_vault",
        "client_id": refresh["client_id"],
        "identity": identity_kind,
        "refresh_entries": 1,
        "secret_value_exposed": False,
    }


def _write_safe_evidence(path: str, payload: dict[str, Any]) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _append_github_env(path: str, *, state_path: Path, client_id: str, source: str) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"MSAL_STORAGE_STATE_PATH={state_path}\n")
        handle.write(f"MSAL_BOOTSTRAP_CLIENT_ID={client_id}\n")
        handle.write(f"PLANNER_TEAMS_SESSION_SOURCE={source}\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("load", "persist"))
    parser.add_argument("--vault-name", required=True)
    parser.add_argument("--state-path", required=True)
    parser.add_argument("--session-secret-name", default=DEFAULT_SESSION_SECRET)
    parser.add_argument("--client-id-secret-name", default=DEFAULT_CLIENT_ID_SECRET)
    parser.add_argument("--legacy-state-env", default="WSJF_MSAL_STORAGE_STATE_B64")
    parser.add_argument("--github-env", default="")
    parser.add_argument("--evidence-path", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        store = KeyVaultSessionStore(args.vault_name)
        state_path = Path(args.state_path)
        if args.action == "load":
            result = load_state(
                store,
                state_path=state_path,
                session_secret_name=args.session_secret_name,
                client_id_secret_name=args.client_id_secret_name,
                legacy_b64=os.getenv(args.legacy_state_env, ""),
            )
            _append_github_env(
                args.github_env,
                state_path=state_path,
                client_id=str(result["client_id"]),
                source=str(result["source"]),
            )
        else:
            result = persist_state(
                store,
                state_path=state_path,
                session_secret_name=args.session_secret_name,
                client_id_secret_name=args.client_id_secret_name,
            )
        _write_safe_evidence(args.evidence_path, result)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except SessionStoreError as exc:
        result = {
            "status": "blocked",
            "reason": str(exc),
            "secret_value_exposed": False,
        }
        _write_safe_evidence(args.evidence_path, result)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 20


if __name__ == "__main__":
    raise SystemExit(main())
