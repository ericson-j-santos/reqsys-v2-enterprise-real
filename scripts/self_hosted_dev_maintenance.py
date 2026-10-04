#!/usr/bin/env python3
"""Read-only maintenance guard for the activated portable PC24x7 DEV runtime.

This module never writes or activates the marker, starts containers, changes
tunnels, publishes a locator, reads secrets, or reports a usable application.
A present but invalid marker blocks the legacy maintenance path.
"""
from __future__ import annotations

import json
import os
import re
import socket
import stat
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

HOST = "DESKTOP-PDQK954"
PROJECT = "reqsys-dev-selfhosted"
INSTANCE = "pc24x7-selfhost-dev-v1"
MARKER_NAME = "self-hosted-dev-active.json"
GATEWAY = "http://127.0.0.1:18080"
SERVICES = ("db", "redis", "api", "frontend", "gateway", "caddy")
SHA_RE = re.compile(r"[0-9a-f]{40}")
ID_RE = re.compile(r"[0-9a-f]{64}")
INSPECT_FORMAT = (
    '{"id":{{json .Id}},"name":{{json .Name}},'
    '"labels":{{json .Config.Labels}},"state":{{json .State}}}'
)
REQUIRED_ENDPOINTS = (
    "/api/health",
    "/api/runtime/health",
    "/api/runtime/readiness",
    "/api/runtime/build-info",
)


class PortableRuntimeError(RuntimeError):
    def __init__(self, code: str) -> None:
        if not re.fullmatch(r"[a-z0-9_]+", code):
            code = "portable_runtime_check_failed"
        self.code = code
        super().__init__(code)


def marker_path() -> Path | None:
    raw = os.environ.get("LOCALAPPDATA", "").strip()
    if not raw:
        if os.name == "nt":
            raise PortableRuntimeError("portable_runtime_localappdata_missing")
        return None
    base = Path(raw)
    if not base.is_absolute():
        raise PortableRuntimeError("portable_runtime_localappdata_invalid")
    return base / "ReqSys" / "RuntimeSupervisor" / MARKER_NAME


def _check_nonlink(path: Path, *, required: bool, directory: bool = False) -> bool:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        if required:
            raise PortableRuntimeError("portable_runtime_marker_missing") from None
        return False
    except OSError:
        raise PortableRuntimeError("portable_runtime_marker_unreadable") from None
    if stat.S_ISLNK(metadata.st_mode) or (
        getattr(metadata, "st_file_attributes", 0) & 0x400
    ):
        raise PortableRuntimeError("portable_runtime_marker_reparse_blocked")
    if directory and not stat.S_ISDIR(metadata.st_mode):
        raise PortableRuntimeError("portable_runtime_marker_ancestor_not_directory")
    return True


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PortableRuntimeError("portable_runtime_json_duplicate_key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise PortableRuntimeError("portable_runtime_json_nonfinite_value")


def _load_json(raw: bytes) -> Any:
    return json.loads(
        raw.decode("utf-8"), object_pairs_hook=_unique_pairs,
        parse_constant=_reject_constant,
    )


def read_marker() -> dict[str, Any] | None:
    path = marker_path()
    if path is None:
        return None
    # Check every existing ancestor from the filesystem root. A redirected
    # LOCALAPPDATA or broken/reparse marker must never mean "legacy mode".
    for parent in reversed(path.parents):
        if not _check_nonlink(parent, required=False, directory=True):
            return None
    if not _check_nonlink(path, required=False):
        return None
    try:
        if not path.is_file() or path.stat().st_size > 4096:
            raise PortableRuntimeError("portable_runtime_marker_size_invalid")
        with path.open("rb") as stream:
            raw = stream.read(4097)
        if len(raw) > 4096:
            raise PortableRuntimeError("portable_runtime_marker_size_invalid")
        payload = _load_json(raw)
    except PortableRuntimeError:
        raise
    except (OSError, UnicodeError, ValueError):
        raise PortableRuntimeError("portable_runtime_marker_invalid_json") from None
    allowed = {
        "schema_version", "host", "environment", "project", "instance", "source_sha"
    }
    if not isinstance(payload, dict) or set(payload) != allowed:
        raise PortableRuntimeError("portable_runtime_marker_schema_invalid")
    if (
        payload["schema_version"] != "1.0.0"
        or payload["host"] != HOST
        or payload["environment"] != "dev"
        or payload["project"] != PROJECT
        or payload["instance"] != INSTANCE
        or not isinstance(payload["source_sha"], str)
        or SHA_RE.fullmatch(payload["source_sha"]) is None
    ):
        raise PortableRuntimeError("portable_runtime_marker_identity_invalid")
    return payload


def _require_host() -> None:
    if os.name != "nt" or socket.gethostname().casefold() != HOST.casefold():
        raise PortableRuntimeError("portable_runtime_host_mismatch")


def _remaining(deadline: float, maximum: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise PortableRuntimeError("portable_runtime_check_timeout")
    return min(maximum, remaining)


def _inspect(service: str, deadline: float) -> dict[str, Any]:
    # Only six fixed Compose service names are inspected. No argv from marker.
    if service not in SERVICES:
        raise PortableRuntimeError("portable_runtime_service_not_allowed")
    name = f"{PROJECT}-{service}-1"
    try:
        completed = subprocess.run(
            ["docker", "inspect", "--format", INSPECT_FORMAT, name],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            timeout=_remaining(deadline, 12),
            check=False,
            shell=False,
        )
        if completed.returncode != 0 or len(completed.stdout) > 32768:
            raise PortableRuntimeError("portable_runtime_container_unavailable")
        payload = _load_json(completed.stdout.encode("utf-8"))
    except PortableRuntimeError:
        raise
    except (OSError, ValueError, UnicodeError, subprocess.TimeoutExpired):
        raise PortableRuntimeError("portable_runtime_container_inspection_failed") from None
    if not isinstance(payload, dict):
        raise PortableRuntimeError("portable_runtime_container_inspection_failed")
    labels = payload.get("labels") or {}
    state = payload.get("state") or {}
    if not isinstance(labels, dict) or not isinstance(state, dict):
        raise PortableRuntimeError("portable_runtime_container_inspection_failed")
    if (
        ID_RE.fullmatch(str(payload.get("id") or "")) is None
        or payload.get("name") != "/" + name
        or labels.get("com.docker.compose.project") != PROJECT
        or labels.get("com.docker.compose.service") != service
        or labels.get("io.reqsys.selfhost.instance") != INSTANCE
    ):
        raise PortableRuntimeError("portable_runtime_container_identity_mismatch")
    if (
        state.get("Running") is not True
        or state.get("Paused") is True
        or state.get("Restarting") is True
        or state.get("Dead") is True
    ):
        raise PortableRuntimeError("portable_runtime_container_not_running")
    health = state.get("Health")
    if service in ("db", "api") and not isinstance(health, dict):
        raise PortableRuntimeError("portable_runtime_container_health_missing")
    if health is not None and (not isinstance(health, dict) or health.get("Status") != "healthy"):
        raise PortableRuntimeError("portable_runtime_container_unhealthy")
    return {
        "service": service, "running": True,
        "health_configured": health is not None,
        "healthy": True if health is not None else None,
    }


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirects())


def _get(path: str, deadline: float, *, json_body: bool = False) -> tuple[int, Any]:
    allowed = {*REQUIRED_ENDPOINTS, "/task-console", "/@vite/client"}
    if path not in allowed:
        raise PortableRuntimeError("portable_runtime_endpoint_not_allowed")
    request = urllib.request.Request(
        GATEWAY + path,
        headers={"User-Agent": "ReqSysPortableDevMaintenance/1.0", "Accept": "*/*"},
    )
    try:
        with _OPENER.open(request, timeout=_remaining(deadline, 8)) as response:
            status = int(response.status)
            raw = response.read(524289)
            content_type = str(response.headers.get("Content-Type") or "")
    except urllib.error.HTTPError as exc:
        return int(exc.code), None
    except (OSError, urllib.error.URLError, TimeoutError):
        raise PortableRuntimeError("portable_runtime_endpoint_unavailable") from None
    if len(raw) > 524288:
        raise PortableRuntimeError("portable_runtime_response_too_large")
    if json_body:
        try:
            body = _load_json(raw)
        except (UnicodeError, ValueError):
            raise PortableRuntimeError("portable_runtime_response_invalid_json") from None
        if not isinstance(body, dict):
            raise PortableRuntimeError("portable_runtime_response_invalid_json")
        return status, body
    if path == "/task-console":
        try:
            html = raw.decode("utf-8")
        except UnicodeError:
            raise PortableRuntimeError("portable_runtime_frontend_invalid") from None
        static = (
            "text/html" in content_type.lower()
            and "/assets/" in html
            and "/src/main.js" not in html
        )
        return status, static
    return status, None


def _health_data(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    if (
        payload.get("success") is not True
        or payload.get("errors") != []
        or not isinstance(payload.get("data"), dict)
    ):
        raise PortableRuntimeError("portable_runtime_health_envelope_invalid")
    data = payload["data"]
    if data.get("service") != "reqsys-api":
        raise PortableRuntimeError("portable_runtime_health_service_mismatch")
    # Reject explicit negative flags even when an older status field says ok.
    for flag in ("ready", "healthy", "available", "database_ok"):
        if flag in data and data[flag] is not True:
            raise PortableRuntimeError("portable_runtime_health_negative_flag")
    checks = data.get("checks")
    if checks is not None:
        if not isinstance(checks, dict) or not checks:
            raise PortableRuntimeError("portable_runtime_health_checks_invalid")
        if any(value is not True and value not in ("ok", "healthy", "ready", "available")
               for value in checks.values()):
            raise PortableRuntimeError("portable_runtime_health_check_failed")
    if endpoint == "/api/health":
        database = data.get("database")
        if (
            data.get("status") != "ok"
            or not isinstance(database, dict)
            or database.get("status") != "ok"
        ):
            raise PortableRuntimeError("portable_runtime_database_health_failed")
    elif endpoint in ("/api/runtime/health", "/api/runtime/readiness"):
        expected_status, expected_check = (
            ("ok", "health") if endpoint.endswith("/health")
            else ("ready", "readiness")
        )
        if (
            data.get("schema_version") != "1.1.0"
            or data.get("environment") != "desenvolvimento"
            or data.get("status") != expected_status
            or data.get("check") != expected_check
        ):
            raise PortableRuntimeError("portable_runtime_health_payload_invalid")
    elif endpoint == "/api/runtime/build-info":
        if data.get("environment") != "desenvolvimento":
            raise PortableRuntimeError("portable_runtime_build_environment_mismatch")
    else:
        raise PortableRuntimeError("portable_runtime_endpoint_not_allowed")
    return data


def verify_if_active(expected_sha: str | None = None) -> dict[str, Any] | None:
    marker = read_marker()
    if marker is None:
        return None
    _require_host()
    if expected_sha is not None and expected_sha != marker["source_sha"]:
        raise PortableRuntimeError("portable_runtime_expected_sha_mismatch")
    deadline = time.monotonic() + 110
    services = [_inspect(service, deadline) for service in SERVICES]
    build = None
    for endpoint in REQUIRED_ENDPOINTS:
        status, payload = _get(endpoint, deadline, json_body=True)
        if status != 200:
            raise PortableRuntimeError("portable_runtime_health_contract_failed")
        data = _health_data(endpoint, payload)
        if endpoint == "/api/runtime/build-info":
            build = data
    if not isinstance(build, dict) or build.get("build_sha") != marker["source_sha"]:
        raise PortableRuntimeError("portable_runtime_build_sha_mismatch")
    frontend_status, static = _get("/task-console", deadline)
    vite_status, _ = _get("/@vite/client", deadline)
    if frontend_status != 200 or static is not True or vite_status != 404:
        raise PortableRuntimeError("portable_runtime_static_frontend_contract_failed")
    return {
        "schema_version": "1.0.0",
        "status": "maintenance_verified",
        "runtime_provider": "self_hosted_dev",
        "environment": "dev",
        "host": HOST,
        "project": PROJECT,
        "instance": INSTANCE,
        "expected_sha": marker["source_sha"],
        "build_sha": marker["source_sha"],
        "maintenance_verified": True,
        "maintenance_read_only": True,
        "legacy_runtime_touched": False,
        "containers": services,
        "local_runtime_contract_ready": True,
        "frontend_static": True,
        "vite_hmr_exposed": False,
        "locator_published": False,
        "public_ingress_verified": False,
        "authenticated_flow_verified": False,
        "usable": False,
        "production_touched": False,
        "secrets_read": False,
        "secret_value_exposed": False,
    }


def control_if_active(expected_sha=None, *, apply=False, publish=False, sign_only_output=None):
    """Use the receipt-bound candidate controller only after an active marker exists."""
    # Preserve the absent/invalid-marker boundary before importing dependencies.
    marker = read_marker()
    if marker is None:
        return None
    if expected_sha is not None and expected_sha != marker["source_sha"]:
        raise PortableRuntimeError("portable_cutover_expected_sha_mismatch")
    try:
        from scripts import self_hosted_dev_candidate_control as candidate
    except ModuleNotFoundError:
        import self_hosted_dev_candidate_control as candidate
    try:
        return candidate.Controller(marker["source_sha"]).maintain(
            marker, publish=publish, apply=apply, sign_only_output=sign_only_output)
    except PortableRuntimeError:
        raise
    except Exception:
        raise PortableRuntimeError("portable_cutover_controller_failed") from None
