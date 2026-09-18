#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_URL = "http://127.0.0.1:8210"
CONTAINER = "wt-pc24x7-piloto-api-1"
ADMIN_EMAIL = "ericsonjosedossantos@tieri659.onmicrosoft.com"
SECRET_MOUNT_TARGET = "/run/secrets/cofre_keyring_passphrase"
DATA_MOUNT_TARGET = "/data"
ALLOWED_ENVIRONMENTS = {"dev", "development", "desenvolvimento"}
REQUIRED_BEFORE_ACTIONS = {
    "COFRE_TOKEN_CRIADO",
    "COFRE_SEGREDO_GRAVADO",
    "COFRE_SEGREDO_LIDO",
}
REQUIRED_AFTER_ACTIONS = {
    "COFRE_SEGREDO_LIDO",
    "COFRE_SEGREDO_REMOVIDO",
    "COFRE_TOKEN_REVOGADO",
}


class E2EError(RuntimeError):
    pass


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _data(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("data", payload)
    return value if isinstance(value, dict) else {}


def request_json(
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    expected: tuple[int, ...] = (200,),
    timeout: int = 30,
) -> tuple[int, dict[str, Any]]:
    request_headers = {"Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    raw_body = None
    if body is not None:
        raw_body = json.dumps(body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    req = Request(BASE_URL + path, data=raw_body, headers=request_headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
            status = int(response.status)
    except HTTPError as exc:
        status = int(exc.code)
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"detail": raw[:300]}
    except (URLError, TimeoutError) as exc:
        raise E2EError(f"http_unreachable:{type(exc).__name__}") from exc
    if status not in expected:
        detail = payload.get("detail") or payload.get("message") or "unexpected_response"
        raise E2EError(f"{method} {path}:http_{status}:{detail}")
    return status, payload


def run_docker(args: list[str], *, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise E2EError(f"docker_failed:{args[0]}:exit_{completed.returncode}")
    return completed


def inspect_runtime(expected_sha: str) -> dict[str, Any]:
    payload = json.loads(run_docker(["inspect", CONTAINER]).stdout)
    if not isinstance(payload, list) or len(payload) != 1:
        raise E2EError("docker_inspect_invalid")
    item = payload[0]
    config = item.get("Config") or {}
    labels = config.get("Labels") or {}
    env_items = config.get("Env") or []
    mounts = item.get("Mounts") or []
    env_map = {}
    for raw in env_items:
        if "=" in raw:
            key, value = raw.split("=", 1)
            env_map[key] = value

    if labels.get("com.docker.compose.service") != "api":
        raise E2EError("runtime_service_not_api")
    if labels.get("com.docker.compose.project") != "wt-pc24x7-piloto":
        raise E2EError("runtime_project_mismatch")
    if env_map.get("GITHUB_SHA") != expected_sha:
        raise E2EError("runtime_sha_mismatch")

    has_secret_mount = any(
        str(m.get("Destination")) == SECRET_MOUNT_TARGET and bool(m.get("RW")) is False
        for m in mounts
    )
    has_data_volume = any(
        str(m.get("Destination")) == DATA_MOUNT_TARGET
        and str(m.get("Type")) == "volume"
        and bool(m.get("RW")) is True
        for m in mounts
    )
    command_text = " ".join(str(x) for x in (config.get("Cmd") or []))
    exports_secret = "COFRE_KEYRING_PASSPHRASE" in command_text and SECRET_MOUNT_TARGET in command_text
    if not has_secret_mount:
        raise E2EError("cofre_secret_mount_missing")
    if not has_data_volume:
        raise E2EError("cofre_data_volume_missing")
    if not exports_secret:
        raise E2EError("cofre_passphrase_export_missing")
    return {
        "project": labels.get("com.docker.compose.project"),
        "service": labels.get("com.docker.compose.service"),
        "runtime_sha": env_map.get("GITHUB_SHA"),
        "secret_mount_read_only": True,
        "data_volume_persistent": True,
        "passphrase_value_observed": False,
    }


def wait_health(timeout_seconds: int = 120) -> int:
    deadline = time.monotonic() + timeout_seconds
    last_status = 0
    while time.monotonic() < deadline:
        try:
            status, payload = request_json("GET", "/health", expected=(200,), timeout=5)
            data = _data(payload)
            if status == 200 and str(data.get("status") or "").lower() in {"ok", "healthy"}:
                return status
            last_status = status
        except E2EError:
            pass
        time.sleep(2)
    raise E2EError(f"health_timeout:last_status_{last_status}")


def mint_admin_jwt(correlation_id: str) -> str:
    _, config_payload = request_json(
        "GET",
        "/v1/auth/config",
        headers={"X-Correlation-Id": correlation_id + "-auth-config"},
    )
    config = _data(config_payload)
    environment = str(config.get("environment") or "").strip().lower()
    if environment not in ALLOWED_ENVIRONMENTS:
        raise E2EError(f"non_dev_environment:{environment or 'unknown'}")
    if config.get("demo_login_enabled") is not True:
        raise E2EError("dev_demo_login_disabled")
    _, login_payload = request_json(
        "POST",
        "/v1/auth/login",
        headers={"X-Correlation-Id": correlation_id + "-login"},
        body={"email": ADMIN_EMAIL},
    )
    login = _data(login_payload)
    token = str(login.get("access_token") or "").strip()
    user = login.get("usuario") if isinstance(login.get("usuario"), dict) else {}
    if not token or str(user.get("papel") or "").lower() != "admin":
        raise E2EError("dev_admin_login_invalid")
    _, session_payload = request_json(
        "GET",
        "/v1/auth/session",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Correlation-Id": correlation_id + "-session",
        },
    )
    if str(_data(session_payload).get("papel") or "").lower() != "admin":
        raise E2EError("dev_admin_session_invalid")
    return token


def admin_headers(token: str, correlation_id: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-Correlation-Id": correlation_id,
    }


def audit_actions(token: str, correlation_id: str) -> set[str]:
    query = urlencode({"entidade": "cofre_segredo", "limit": 100})
    _, payload = request_json(
        "GET",
        f"/v1/auditoria/eventos?{query}",
        headers=admin_headers(token, correlation_id),
    )
    events = _data(payload).get("dados") or []
    return {
        str(item.get("acao"))
        for item in events
        if isinstance(item, dict) and item.get("correlation_id") == correlation_id
    }


def execute(expected_sha: str, correlation_id: str, evidence_file: Path) -> dict[str, Any]:
    runtime = inspect_runtime(expected_sha)
    wait_health()
    admin_token = mint_admin_jwt(correlation_id)

    _, status_payload = request_json(
        "GET",
        "/v1/cofre/status",
        headers=admin_headers(admin_token, correlation_id),
    )
    status_before = _data(status_payload)
    initialized_by_run = False
    if not bool(status_before.get("inicializado")):
        _, init_payload = request_json(
            "POST",
            "/v1/cofre/init",
            headers=admin_headers(admin_token, correlation_id),
        )
        initialized_by_run = _data(init_payload).get("status") == "inicializado"

    _, status_payload = request_json(
        "GET",
        "/v1/cofre/status",
        headers=admin_headers(admin_token, correlation_id),
    )
    if not bool(_data(status_payload).get("inicializado")):
        raise E2EError("vault_not_initialized")

    test_key = f"REQSYS_EVIDENCE_DEV_{uuid.uuid4().hex.upper()}"
    test_value = uuid.uuid4().hex + uuid.uuid4().hex
    token_id: int | None = None
    vault_token = ""
    cleanup = {"secret_deleted": False, "token_revoked": False}

    try:
        _, token_payload = request_json(
            "POST",
            "/v1/cofre/tokens",
            headers=admin_headers(admin_token, correlation_id),
            body={
                "label": f"runtime-evidence-dev-{correlation_id[-12:]}",
                "key_patterns": [test_key],
            },
        )
        token_data = _data(token_payload)
        token_id = int(token_data["id"])
        vault_token = str(token_data["token"])

        request_json(
            "POST",
            "/v1/cofre/segredos",
            headers=admin_headers(admin_token, correlation_id),
            body={"key": test_key, "value": test_value},
        )
        _, read_payload = request_json(
            "GET",
            f"/v1/cofre/segredos/{test_key}",
            headers={
                "X-Vault-Token": vault_token,
                "X-Correlation-Id": correlation_id,
            },
        )
        if _data(read_payload).get("value") != test_value:
            raise E2EError("pre_restart_value_mismatch")

        request_json(
            "GET",
            f"/v1/cofre/segredos/{test_key}_OUT_OF_SCOPE",
            headers={
                "X-Vault-Token": vault_token,
                "X-Correlation-Id": correlation_id,
            },
            expected=(403,),
        )
        before_actions = audit_actions(admin_token, correlation_id)
        missing_before = sorted(REQUIRED_BEFORE_ACTIONS - before_actions)
        if missing_before:
            raise E2EError("audit_before_missing:" + ",".join(missing_before))

        run_docker(["restart", CONTAINER], timeout=120)
        wait_health()
        admin_token = mint_admin_jwt(correlation_id + "-postrestart")

        _, post_status_payload = request_json(
            "GET",
            "/v1/cofre/status",
            headers=admin_headers(admin_token, correlation_id),
        )
        if not bool(_data(post_status_payload).get("inicializado")):
            raise E2EError("vault_not_initialized_after_restart")

        _, post_read_payload = request_json(
            "GET",
            f"/v1/cofre/segredos/{test_key}",
            headers={
                "X-Vault-Token": vault_token,
                "X-Correlation-Id": correlation_id,
            },
        )
        if _data(post_read_payload).get("value") != test_value:
            raise E2EError("post_restart_value_mismatch")

        request_json(
            "DELETE",
            f"/v1/cofre/segredos/{test_key}",
            headers=admin_headers(admin_token, correlation_id),
        )
        cleanup["secret_deleted"] = True

        request_json(
            "GET",
            f"/v1/cofre/segredos/{test_key}",
            headers={
                "X-Vault-Token": vault_token,
                "X-Correlation-Id": correlation_id,
            },
            expected=(404,),
        )

        request_json(
            "DELETE",
            f"/v1/cofre/tokens/{token_id}",
            headers=admin_headers(admin_token, correlation_id),
        )
        cleanup["token_revoked"] = True

        request_json(
            "GET",
            f"/v1/cofre/segredos/{test_key}",
            headers={
                "X-Vault-Token": vault_token,
                "X-Correlation-Id": correlation_id,
            },
            expected=(401,),
        )

        after_actions = audit_actions(admin_token, correlation_id)
        missing_after = sorted(REQUIRED_AFTER_ACTIONS - after_actions)
        if missing_after:
            raise E2EError("audit_after_missing:" + ",".join(missing_after))

        evidence = {
            "schema_version": "1.0.0",
            "contract": "reqsys-cofre-dev-pc24x7-runtime-e2e",
            "ok": True,
            "environment": "dev",
            "runtime": runtime,
            "correlation_id": correlation_id,
            "initialized_by_run": initialized_by_run,
            "before_restart": {
                "write_read_match": True,
                "scope_denial_http_403": True,
                "audit_actions_found": sorted(REQUIRED_BEFORE_ACTIONS),
            },
            "restart": {
                "container": CONTAINER,
                "health_recovered": True,
            },
            "after_restart": {
                "vault_initialized": True,
                "persistence_match": True,
                "post_cleanup_http_404": True,
                "revoked_token_http_401": True,
                "audit_actions_found": sorted(REQUIRED_AFTER_ACTIONS),
                "cleanup_completed": True,
            },
            "secret_key_sha256": _sha256(test_key),
            "secret_value_sha256": _sha256(test_value),
            "scoped_token_id": token_id,
            "sensitive_values_exposed": False,
            "production_touched": False,
        }
        evidence_file.parent.mkdir(parents=True, exist_ok=True)
        evidence_file.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return evidence
    finally:
        if admin_token:
            if not cleanup["secret_deleted"]:
                try:
                    request_json(
                        "DELETE",
                        f"/v1/cofre/segredos/{test_key}",
                        headers=admin_headers(admin_token, correlation_id),
                    )
                except Exception:
                    pass
            if token_id is not None and not cleanup["token_revoked"]:
                try:
                    request_json(
                        "DELETE",
                        f"/v1/cofre/tokens/{token_id}",
                        headers=admin_headers(admin_token, correlation_id),
                    )
                except Exception:
                    pass


def self_test() -> int:
    sample = [{
        "Config": {
            "Env": ["GITHUB_SHA=abc123"],
            "Cmd": ["/bin/sh", "-ec", f"export COFRE_KEYRING_PASSPHRASE=\"$(cat {SECRET_MOUNT_TARGET})\""],
            "Labels": {
                "com.docker.compose.service": "api",
                "com.docker.compose.project": "wt-pc24x7-piloto",
            },
        },
        "Mounts": [
            {"Destination": SECRET_MOUNT_TARGET, "Type": "bind", "RW": False},
            {"Destination": DATA_MOUNT_TARGET, "Type": "volume", "RW": True},
        ],
    }]
    original = run_docker
    try:
        globals()["run_docker"] = lambda args, timeout=120: subprocess.CompletedProcess(
            ["docker", *args], 0, stdout=json.dumps(sample), stderr=""
        )
        result = inspect_runtime("abc123")
        assert result["secret_mount_read_only"] is True
        assert result["data_volume_persistent"] is True
        assert "passphrase" not in json.dumps(result).lower() or result["passphrase_value_observed"] is False
    finally:
        globals()["run_docker"] = original
    print(json.dumps({"self_test": True}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="E2E real do Cofre DEV PC24x7")
    parser.add_argument("--expected-runtime-sha")
    parser.add_argument("--correlation-id")
    parser.add_argument("--evidence-file", default=".tmp/cofre1760-runtime-e2e.json")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if not args.expected_runtime_sha or not args.correlation_id:
        parser.error("--expected-runtime-sha e --correlation-id são obrigatórios")
    try:
        result = execute(
            args.expected_runtime_sha,
            args.correlation_id,
            Path(args.evidence_file),
        )
        print(json.dumps({
            "ok": result["ok"],
            "environment": result["environment"],
            "runtime_sha": result["runtime"]["runtime_sha"],
            "persistence_match": result["after_restart"]["persistence_match"],
            "cleanup_completed": result["after_restart"]["cleanup_completed"],
            "sensitive_values_exposed": result["sensitive_values_exposed"],
            "production_touched": result["production_touched"],
        }))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc), "production_touched": False}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
