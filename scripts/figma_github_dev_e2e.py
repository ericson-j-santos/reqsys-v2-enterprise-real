#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

BASE_URL = "http://127.0.0.1:8210"
CONTAINER = "wt-pc24x7-piloto-api-1"
PROJECT = "wt-pc24x7-piloto"
SERVICE = "api"
EXPECTED_HOST = "DESKTOP-PDQK954"
ADMIN_EMAIL = "ericsonjosedossantos@tieri659.onmicrosoft.com"
FIGMA_FILE_KEY = "1iA8PiHX7qMnYHBDTdt0fY"
FIGMA_NODE_ID = "1:44"
GITHUB_REPO = "ericson-j-santos/reqsys-v2-enterprise-real"
ALLOWED_ENVIRONMENTS = {"dev", "development", "desenvolvimento"}


class E2EError(RuntimeError):
    pass


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _data(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("data", payload)
    return value if isinstance(value, dict) else {}


def request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    expected: tuple[int, ...] = (200,),
    timeout: int = 30,
) -> tuple[int, dict[str, Any], dict[str, str]]:
    request_headers = {"Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    raw_body = None
    if body is not None:
        raw_body = json.dumps(body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    req = Request(url, data=raw_body, headers=request_headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
            status = int(response.status)
            response_headers = {key.lower(): value for key, value in response.headers.items()}
    except HTTPError as exc:
        status = int(exc.code)
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"detail": raw[:300]}
        response_headers = {key.lower(): value for key, value in (exc.headers.items() if exc.headers else [])}
    except (URLError, TimeoutError, OSError) as exc:
        raise E2EError(f"http_unreachable:{type(exc).__name__}") from exc
    if status not in expected:
        detail = payload.get("detail") or payload.get("message") or "unexpected_response"
        raise E2EError(f"{method} {url}:http_{status}:{str(detail)[:240]}")
    return status, payload, response_headers


def runtime_request(
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    expected: tuple[int, ...] = (200,),
) -> tuple[int, dict[str, Any], dict[str, str]]:
    return request_json(method, BASE_URL + path, headers=headers, body=body, expected=expected)


def run_docker(args: list[str], timeout: int = 180) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        shell=False,
    )
    if result.returncode != 0:
        raise E2EError(f"docker_{args[0]}_failed:exit_{result.returncode}")
    return result


def inspect_runtime(expected_sha: str) -> dict[str, Any]:
    if socket.gethostname().casefold() != EXPECTED_HOST.casefold():
        raise E2EError(f"host_mismatch:{socket.gethostname()}")
    payload = json.loads(run_docker(["inspect", CONTAINER]).stdout)
    if not isinstance(payload, list) or len(payload) != 1:
        raise E2EError("container_inspect_invalid")
    item = payload[0]
    config = item.get("Config") or {}
    labels = config.get("Labels") or {}
    env_map: dict[str, str] = {}
    for raw in config.get("Env") or []:
        if "=" in raw:
            key, value = raw.split("=", 1)
            env_map[key] = value
    if labels.get("com.docker.compose.project") != PROJECT:
        raise E2EError("compose_project_mismatch")
    if labels.get("com.docker.compose.service") != SERVICE:
        raise E2EError("compose_service_mismatch")
    runtime_sha = str(env_map.get("GITHUB_SHA") or "")
    if runtime_sha != expected_sha:
        raise E2EError(f"runtime_sha_mismatch:{runtime_sha or 'missing'}")
    state = item.get("State") or {}
    health = (state.get("Health") or {}).get("Status") or state.get("Status") or "unknown"
    return {"runtime_sha": runtime_sha, "health": str(health).lower()}


def wait_runtime(expected_sha: str, timeout: int = 180) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last = "unknown"
    while time.monotonic() < deadline:
        try:
            evidence = inspect_runtime(expected_sha)
            last = evidence["health"]
            if last == "healthy":
                runtime_request("GET", "/health", expected=(200,))
                return evidence
        except E2EError:
            pass
        time.sleep(2)
    raise E2EError(f"runtime_health_timeout:{last}")


def mint_admin_jwt(correlation_id: str) -> str:
    _, config_payload, _ = runtime_request(
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
    _, login_payload, _ = runtime_request(
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
    return token


def admin_headers(token: str, correlation_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Correlation-Id": correlation_id}


def write_default(token: str, correlation_id: str, key: str, value: str) -> None:
    runtime_request(
        "POST",
        "/v1/cofre/segredos",
        headers=admin_headers(token, correlation_id),
        body={"key": key, "value": value},
    )


def create_secret_probe_token(admin_token: str, correlation_id: str) -> tuple[int, str]:
    _, payload, _ = runtime_request(
        "POST",
        "/v1/cofre/tokens",
        headers=admin_headers(admin_token, correlation_id),
        body={
            "label": f"figma-e2e-{correlation_id[-12:]}",
            "key_patterns": ["FIGMA_ACCESS_TOKEN", "GITHUB_TOKEN"],
        },
    )
    data = _data(payload)
    return int(data["id"]), str(data["token"])


def read_vault_secret(vault_token: str, correlation_id: str, key: str) -> str:
    _, payload, _ = runtime_request(
        "GET",
        f"/v1/cofre/segredos/{quote(key, safe='')}",
        headers={"X-Vault-Token": vault_token, "X-Correlation-Id": correlation_id},
    )
    value = str(_data(payload).get("value") or "")
    if not value:
        raise E2EError(f"secret_empty:{key}")
    return value


def revoke_probe_token(admin_token: str, correlation_id: str, token_id: int) -> None:
    runtime_request(
        "DELETE",
        f"/v1/cofre/tokens/{token_id}",
        headers=admin_headers(admin_token, correlation_id),
        expected=(200, 404),
    )


def figma_comments(figma_token: str) -> list[dict[str, Any]]:
    _, payload, _ = request_json(
        "GET",
        f"https://api.figma.com/v1/files/{quote(FIGMA_FILE_KEY, safe='')}/comments",
        headers={"X-Figma-Token": figma_token},
    )
    comments = payload.get("comments") or []
    return [item for item in comments if isinstance(item, dict)]


def github_issue(issue_number: int, token: str) -> dict[str, Any]:
    _, payload, _ = request_json(
        "GET",
        f"https://api.github.com/repos/{GITHUB_REPO}/issues/{issue_number}",
        headers={
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    return payload


def sync_payload() -> dict[str, Any]:
    return {
        "mode": "bidirectional",
        "node_ids": [FIGMA_NODE_ID],
        "include_comments": False,
        "include_frames": True,
        "include_dev_resources": False,
    }


def execute(expected_sha: str, correlation_id: str, evidence_file: Path) -> dict[str, Any]:
    runtime_before = inspect_runtime(expected_sha)
    wait_runtime(expected_sha)

    admin_token = mint_admin_jwt(correlation_id)
    _, vault_status_payload, _ = runtime_request(
        "GET",
        "/v1/cofre/status",
        headers=admin_headers(admin_token, correlation_id + "-vault-status"),
    )
    if not bool(_data(vault_status_payload).get("inicializado")):
        raise E2EError("vault_not_initialized")

    # Controle negativo sem efeito externo: enum inválido falha antes de acessar Figma/GitHub.
    runtime_request(
        "POST",
        "/v1/integracoes/figma-github/sync",
        headers=admin_headers(admin_token, correlation_id + "-negative"),
        body={"mode": "invalid-e2e-control"},
        expected=(422,),
    )

    write_default(admin_token, correlation_id + "-default-file", "FIGMA_DEFAULT_FILE_KEY", FIGMA_FILE_KEY)
    write_default(admin_token, correlation_id + "-default-repo", "FIGMA_GITHUB_DEFAULT_REPO", GITHUB_REPO)

    probe_token_id: int | None = None
    figma_token = ""
    try:
        probe_token_id, probe_token = create_secret_probe_token(admin_token, correlation_id + "-probe-token")
        figma_token = read_vault_secret(probe_token, correlation_id + "-figma-secret-check", "FIGMA_ACCESS_TOKEN")
        github_runtime_token = read_vault_secret(probe_token, correlation_id + "-github-secret-check", "GITHUB_TOKEN")
        if not github_runtime_token:
            raise E2EError("github_runtime_token_missing")
        github_runtime_token = ""

        run_docker(["restart", CONTAINER], timeout=120)
        runtime_after = wait_runtime(expected_sha)
        admin_token = mint_admin_jwt(correlation_id + "-after-restart")

        _, config_payload, config_headers = runtime_request(
            "GET",
            "/v1/integracoes/figma-github/config",
            headers={"X-Correlation-Id": correlation_id + "-config"},
        )
        config = _data(config_payload)
        if config != {
            "has_default_file_key": True,
            "has_default_repo": True,
            "sync_enabled": True,
        }:
            raise E2EError(f"figma_config_not_ready:{config}")

        first_status, first_payload, first_headers = runtime_request(
            "POST",
            "/v1/integracoes/figma-github/sync",
            headers=admin_headers(admin_token, correlation_id + "-first"),
            body=sync_payload(),
        )
        first = _data(first_payload)
        links = [link for link in first.get("links") or [] if isinstance(link, dict) and link.get("github_issue_number")]
        if not links:
            raise E2EError("first_sync_issue_link_missing")
        issue_number = int(links[0]["github_issue_number"])

        query = urlencode({"file_key": FIGMA_FILE_KEY, "repo": GITHUB_REPO})
        _, status_payload, _ = runtime_request(
            "GET",
            f"/v1/integracoes/figma-github/status?{query}",
            headers={"X-Correlation-Id": correlation_id + "-status"},
        )
        status_items = _data(status_payload).get("items") or []
        matching = [
            item for item in status_items
            if isinstance(item, dict)
            and str(item.get("figma_node_id") or "") == FIGMA_NODE_ID
            and int(item.get("github_issue_number") or 0) == issue_number
        ]
        if len(matching) != 1:
            raise E2EError(f"runtime_link_count_invalid:{len(matching)}")
        issue_url = str(matching[0].get("github_issue_url") or "")

        github_read_token = os.getenv("E2E_GITHUB_READ_TOKEN", "").strip()
        if not github_read_token:
            raise E2EError("e2e_github_read_token_missing")
        issue = github_issue(issue_number, github_read_token)
        marker = f"<!-- reqsys-figma-sync:file={FIGMA_FILE_KEY};node={FIGMA_NODE_ID};comment= -->"
        if marker not in str(issue.get("body") or ""):
            raise E2EError("github_marker_missing")

        back_message = f"[ReqSys Sync] GitHub #{issue_number} atualizado: {issue_url}".strip()
        comments_after_first = figma_comments(figma_token)
        back_count_first = sum(
            1 for item in comments_after_first
            if str(item.get("message") or item.get("text") or "").strip() == back_message
        )
        if back_count_first != 1:
            raise E2EError(f"figma_back_comment_count_after_first:{back_count_first}")

        _, replay_payload, replay_headers = runtime_request(
            "POST",
            "/v1/integracoes/figma-github/sync",
            headers=admin_headers(admin_token, correlation_id + "-replay"),
            body=sync_payload(),
        )
        replay = _data(replay_payload)
        if int(replay.get("created") or 0) != 0 or int(replay.get("updated") or 0) != 0:
            raise E2EError(
                f"replay_not_idempotent:created={replay.get('created')}:updated={replay.get('updated')}"
            )
        if int(replay.get("skipped") or 0) < 2:
            raise E2EError(f"replay_skip_count_invalid:{replay.get('skipped')}")

        comments_after_replay = figma_comments(figma_token)
        back_count_replay = sum(
            1 for item in comments_after_replay
            if str(item.get("message") or item.get("text") or "").strip() == back_message
        )
        if back_count_replay != 1:
            raise E2EError(f"figma_back_comment_duplicate:{back_count_replay}")

        issue_replay = github_issue(issue_number, github_read_token)
        if int(issue_replay.get("number") or 0) != issue_number:
            raise E2EError("github_issue_identity_changed")

        evidence = {
            "schema_version": "1.0.0",
            "contract": "figma-github-dev-e2e",
            "status": "passed",
            "environment": "dev",
            "runtime_sha": expected_sha,
            "host": EXPECTED_HOST,
            "correlation_id": correlation_id,
            "defaults_configured": True,
            "figma_file_key_sha256": _sha256(FIGMA_FILE_KEY),
            "figma_node_id": FIGMA_NODE_ID,
            "github_repo": GITHUB_REPO,
            "github_issue_number": issue_number,
            "github_issue_url": issue_url,
            "first_sync": {
                "http_status": first_status,
                "created": first.get("created"),
                "updated": first.get("updated"),
                "skipped": first.get("skipped"),
                "conflicts": first.get("conflicts"),
                "warnings_count": len(first.get("warnings") or []),
            },
            "replay": {
                "created": replay.get("created"),
                "updated": replay.get("updated"),
                "skipped": replay.get("skipped"),
                "conflicts": replay.get("conflicts"),
                "warnings_count": len(replay.get("warnings") or []),
                "figma_back_comment_count": back_count_replay,
            },
            "correlation_observed": bool(
                _data(first_payload).get("correlation_id")
                or first_payload.get("meta", {}).get("correlation_id")
                or first_headers.get("x-correlation-id")
                or replay_headers.get("x-correlation-id")
                or config_headers.get("x-correlation-id")
            ),
            "runtime_before": runtime_before,
            "runtime_after": runtime_after,
            "sensitive_values_exposed": False,
            "production_touched": False,
        }
    finally:
        if probe_token_id is not None:
            try:
                admin_token = mint_admin_jwt(correlation_id + "-cleanup")
                revoke_probe_token(admin_token, correlation_id + "-cleanup", probe_token_id)
            except Exception:
                pass
        figma_token = ""

    evidence_file.parent.mkdir(parents=True, exist_ok=True)
    evidence_file.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))
    return evidence


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        evidence = execute(args.expected_sha, args.correlation_id, args.evidence_file)
    except Exception as exc:
        safe = {
            "schema_version": "1.0.0",
            "contract": "figma-github-dev-e2e",
            "status": "blocked",
            "environment": "dev",
            "reason": type(exc).__name__,
            "detail": str(exc)[:300],
            "correlation_id": args.correlation_id,
            "sensitive_values_exposed": False,
            "production_touched": False,
        }
        args.evidence_file.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_file.write_text(json.dumps(safe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(safe, ensure_ascii=False, sort_keys=True))
        return 4
    return 0 if evidence.get("status") == "passed" else 4


if __name__ == "__main__":
    raise SystemExit(main())
