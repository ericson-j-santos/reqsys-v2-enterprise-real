from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from datetime import UTC, datetime
from http.client import HTTPConnection
from http.client import HTTPException as HTTPClientException
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

VALID_PROFILES = {"NORMAL", "ESTUDO"}
PROFILE_PATH_ENV = "NOTERI_HOST_PROFILE_PATH"
AUDIT_PATH_ENV = "NOTERI_HOST_PROFILE_AUDIT_PATH"
EXPECTED_HOST_ENV = "NOTERI_HOST_PROFILE_EXPECTED_HOST"
CONTROL_PLANE_URL_ENV = "NOTERI_CONTROL_PLANE_URL"
DEFAULT_EXPECTED_HOST = "Noteri"
PROFILE_TASK_TYPE = "host.profile.set.v1"
TERMINAL_STATUSES = {"CONCLUÍDO", "BLOQUEADO", "CANCELADO"}
ALLOWED_CONTROL_PLANE_HOSTS = {"host.docker.internal", "127.0.0.1", "localhost"}
CONTROL_PLANE_PORT = 8787
DEFAULT_DEV_CONTROL_PLANE_URL = "http://host.docker.internal:8787"
DEV_ENVIRONMENTS = {"development", "dev", "desenvolvimento"}


class NoteriProfileUnavailable(RuntimeError):
    """O estado canônico do Noteri não está acessível neste runtime."""


class NoteriProfileInvalid(RuntimeError):
    """O estado observado não cumpre o contrato esperado."""


def expected_host() -> str:
    value = (os.getenv(EXPECTED_HOST_ENV) or DEFAULT_EXPECTED_HOST).strip()
    if not value:
        raise NoteriProfileUnavailable("expected host unavailable")
    return value


def _is_containerized() -> bool:
    return Path("/.dockerenv").exists()


def _implicit_dev_control_plane_url() -> str | None:
    if (os.getenv(PROFILE_PATH_ENV) or "").strip():
        return None
    environment = (
        os.getenv("APP_ENV")
        or os.getenv("ENVIRONMENT")
        or "development"
    ).strip().lower().replace("-", "_")
    if environment not in DEV_ENVIRONMENTS or not _is_containerized():
        return None
    return DEFAULT_DEV_CONTROL_PLANE_URL


def control_plane_url() -> str | None:
    raw = (os.getenv(CONTROL_PLANE_URL_ENV) or "").strip()
    if not raw:
        raw = _implicit_dev_control_plane_url() or ""
    if not raw:
        return None
    parsed = urlparse(raw)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in ALLOWED_CONTROL_PLANE_HOSTS
        or parsed.port != CONTROL_PLANE_PORT
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        raise NoteriProfileUnavailable("control plane endpoint is not allowlisted")
    return raw.rstrip("/")


def profile_path() -> Path:
    raw = (os.getenv(PROFILE_PATH_ENV) or "").strip()
    if not raw:
        raise NoteriProfileUnavailable("host profile path unavailable")
    path = Path(raw)
    if not path.parent.is_dir():
        raise NoteriProfileUnavailable("host profile directory unavailable")
    return path


def audit_path() -> Path:
    raw = (os.getenv(AUDIT_PATH_ENV) or "").strip()
    if raw:
        path = Path(raw)
        if not path.parent.is_dir():
            raise NoteriProfileUnavailable("host profile audit directory unavailable")
        return path
    return profile_path().with_name("host-profile-api-audit.jsonl")


def normalize_profile(value: object) -> str:
    profile = str(value or "").strip().upper()
    if profile not in VALID_PROFILES:
        raise ValueError("profile deve ser NORMAL ou ESTUDO")
    return profile


def normalize_correlation_id(value: object) -> str:
    correlation_id = str(value or "").strip()
    if not 8 <= len(correlation_id) <= 128:
        raise ValueError("correlation_id deve ter 8..128 caracteres")
    if "\r" in correlation_id or "\n" in correlation_id:
        raise ValueError("correlation_id inválido")
    return correlation_id


def _validate_host(payload: dict[str, Any]) -> None:
    observed = str(payload.get("host") or "").strip()
    if observed and observed.casefold() != expected_host().casefold():
        raise NoteriProfileInvalid("host profile belongs to another host")


def _control_plane_request(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout: float = 5.0,
) -> dict[str, Any]:
    base = control_plane_url()
    if base is None:
        raise NoteriProfileUnavailable("control plane endpoint unavailable")
    if path not in {"/v1/workers", "/v1/intake"} and not path.startswith("/v1/work-items/"):
        raise NoteriProfileUnavailable("control plane path is not allowlisted")

    normalized_method = str(method or "").strip().upper()
    if normalized_method not in {"GET", "POST"}:
        raise NoteriProfileUnavailable("control plane method is not allowlisted")

    parsed = urlparse(base)
    host = parsed.hostname
    port = parsed.port
    if host is None or port is None:
        raise NoteriProfileUnavailable("control plane endpoint is invalid")

    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        headers["Content-Type"] = "application/json"

    connection = HTTPConnection(host, port, timeout=timeout)
    try:
        connection.request(normalized_method, path, body=data, headers=headers)
        response = connection.getresponse()
        raw = response.read().decode("utf-8")
        if response.status < 200 or response.status >= 300:
            raise NoteriProfileUnavailable("control plane returned non-success status")
    except (HTTPClientException, TimeoutError, OSError) as exc:
        raise NoteriProfileUnavailable("control plane unavailable") from exc
    finally:
        connection.close()
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise NoteriProfileInvalid("control plane returned invalid JSON") from exc
    if not isinstance(decoded, dict):
        raise NoteriProfileInvalid("control plane returned invalid payload")
    return decoded


def _load_control_plane_profile() -> dict[str, Any]:
    payload = _control_plane_request("GET", "/v1/workers")
    workers = payload.get("workers")
    if not isinstance(workers, list):
        raise NoteriProfileInvalid("control plane worker registry is invalid")

    target = expected_host()
    matches = [
        worker
        for worker in workers
        if isinstance(worker, dict)
        and str(worker.get("device_name") or "").casefold() == target.casefold()
    ]
    if len(matches) != 1:
        raise NoteriProfileUnavailable("Noteri worker is not uniquely registered")
    worker = matches[0]
    if (
        worker.get("fresh") is not True
        or worker.get("controller_online") is not True
        or worker.get("auth_valid") is not True
    ):
        raise NoteriProfileUnavailable("Noteri worker is not operationally available")

    profile = normalize_profile(worker.get("profile"))
    return {
        "schema_version": "1",
        "host": target,
        "profile": profile,
        "accepts_new_development": profile == "NORMAL",
        "source": "control_plane",
    }


def _validate_task_result(result: object, requested: str) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise NoteriProfileInvalid("profile task result is invalid")
    if result.get("handler") != PROFILE_TASK_TYPE:
        raise NoteriProfileInvalid("profile task handler mismatch")
    if str(result.get("host") or "").casefold() != expected_host().casefold():
        raise NoteriProfileInvalid("profile task host mismatch")
    if normalize_profile(result.get("profile")) != requested:
        raise NoteriProfileInvalid("profile task result mismatch")
    if result.get("independent_readback") is not True:
        raise NoteriProfileInvalid("profile task lacks independent readback")
    if result.get("control_plane_readback") is not True:
        raise NoteriProfileInvalid("profile task lacks control-plane readback")
    if result.get("accepts_new_development") is not (requested == "NORMAL"):
        raise NoteriProfileInvalid("profile task eligibility mismatch")
    return result


def _set_control_plane_profile(profile: str, correlation_id: str) -> dict[str, Any]:
    before = _load_control_plane_profile()
    changed = before["profile"] != profile
    if not changed:
        after = _load_control_plane_profile()
        if after["profile"] != profile:
            raise NoteriProfileInvalid("independent profile readback mismatch")
        return {
            **after,
            "changed": False,
            "request_correlation_id": correlation_id,
        }

    digest = hashlib.sha256(
        f"noteri-profile|{profile}|{correlation_id}".encode("utf-8")
    ).hexdigest()
    intake = _control_plane_request(
        "POST",
        "/v1/intake",
        {
            "event_id": f"noteri-profile-{digest[:32]}",
            "correlation_id": correlation_id,
            "idempotency_key": f"noteri-profile:{digest}",
            "task_type": PROFILE_TASK_TYPE,
            "payload": {
                "target_host": expected_host(),
                "profile": profile,
                "worker_hint": "builder",
            },
            "risk": 1,
            "max_attempts": 1,
            "lease_seconds": 60,
        },
    )
    item = intake.get("item")
    if not isinstance(item, dict) or not isinstance(item.get("id"), str):
        raise NoteriProfileInvalid("profile task intake is invalid")

    dispatch = intake.get("dispatch")
    if not isinstance(dispatch, dict):
        raise NoteriProfileUnavailable("Noteri worker did not accept the profile task")
    worker = dispatch.get("worker")
    if (
        not isinstance(worker, dict)
        or str(worker.get("device_name") or "").casefold()
        != expected_host().casefold()
    ):
        raise NoteriProfileInvalid("profile task dispatched to unexpected worker")

    item_id = item["id"]
    deadline = time.monotonic() + 15.0
    completed: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        snapshot = _control_plane_request("GET", f"/v1/work-items/{item_id}")
        observed = snapshot.get("item")
        if not isinstance(observed, dict):
            raise NoteriProfileInvalid("profile task status is invalid")
        status = str(observed.get("status") or "")
        if status == "CONCLUÍDO":
            completed = observed
            break
        if status in TERMINAL_STATUSES:
            raise NoteriProfileUnavailable("profile task did not complete")
        time.sleep(0.25)

    if completed is None:
        raise NoteriProfileUnavailable("profile task timed out")

    result = _validate_task_result(completed.get("result"), profile)
    after = _load_control_plane_profile()
    if after["profile"] != profile:
        raise NoteriProfileInvalid("control plane profile readback mismatch")

    return {
        **after,
        "changed": bool(result.get("changed", True)),
        "request_correlation_id": correlation_id,
    }


def load_profile() -> dict[str, Any]:
    if control_plane_url() is not None:
        return _load_control_plane_profile()

    path = profile_path()
    if not path.exists():
        return {
            "schema_version": "1",
            "host": expected_host(),
            "profile": "NORMAL",
            "accepts_new_development": True,
            "source": "default",
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NoteriProfileInvalid("host profile is invalid") from exc
    if not isinstance(payload, dict):
        raise NoteriProfileInvalid("host profile must be a JSON object")
    _validate_host(payload)
    profile = normalize_profile(payload.get("profile"))
    result = dict(payload)
    result["host"] = expected_host()
    result["profile"] = profile
    result["accepts_new_development"] = profile == "NORMAL"
    result["source"] = "file"
    return result


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def append_audit(payload: dict[str, Any]) -> None:
    path = audit_path()
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def set_profile(profile: object, correlation_id: object) -> dict[str, Any]:
    requested = normalize_profile(profile)
    correlation = normalize_correlation_id(correlation_id)

    if control_plane_url() is not None:
        return _set_control_plane_profile(requested, correlation)

    path = profile_path()
    before = load_profile()
    changed = before["profile"] != requested

    if changed:
        payload = {
            "schema_version": "1",
            "host": expected_host(),
            "profile": requested,
            "accepts_new_development": requested == "NORMAL",
            "updated_at": datetime.now(UTC).isoformat(),
            "correlation_id": correlation,
        }
        _atomic_write(path, payload)

    after = load_profile()
    if (
        after["profile"] != requested
        or after["accepts_new_development"] != (requested == "NORMAL")
    ):
        raise NoteriProfileInvalid("independent profile readback mismatch")

    append_audit(
        {
            "timestamp": datetime.now(UTC).isoformat(),
            "host": expected_host(),
            "before_profile": before["profile"],
            "after_profile": after["profile"],
            "changed": changed,
            "correlation_id": correlation,
            "channel": "reqsys_api",
        }
    )
    return {
        **after,
        "changed": changed,
        "request_correlation_id": correlation,
    }
