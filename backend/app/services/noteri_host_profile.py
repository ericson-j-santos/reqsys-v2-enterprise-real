from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

VALID_PROFILES = {"NORMAL", "ESTUDO"}
PROFILE_PATH_ENV = "NOTERI_HOST_PROFILE_PATH"
AUDIT_PATH_ENV = "NOTERI_HOST_PROFILE_AUDIT_PATH"
EXPECTED_HOST_ENV = "NOTERI_HOST_PROFILE_EXPECTED_HOST"
DEFAULT_EXPECTED_HOST = "Noteri"


class NoteriProfileUnavailable(RuntimeError):
    """O estado canônico do Noteri não está materializado neste runtime."""


class NoteriProfileInvalid(RuntimeError):
    """O estado materializado não cumpre o contrato esperado."""


def expected_host() -> str:
    value = (os.getenv(EXPECTED_HOST_ENV) or DEFAULT_EXPECTED_HOST).strip()
    if not value:
        raise NoteriProfileUnavailable("NOTERI_HOST_PROFILE_EXPECTED_HOST vazio")
    return value


def profile_path() -> Path:
    raw = (os.getenv(PROFILE_PATH_ENV) or "").strip()
    if not raw:
        raise NoteriProfileUnavailable(
            "Modo ESTUDO indisponível neste runtime: NOTERI_HOST_PROFILE_PATH não configurado"
        )
    path = Path(raw)
    if not path.parent.is_dir():
        raise NoteriProfileUnavailable(
            "Modo ESTUDO indisponível neste runtime: diretório do perfil não montado"
        )
    return path


def audit_path() -> Path:
    raw = (os.getenv(AUDIT_PATH_ENV) or "").strip()
    if raw:
        path = Path(raw)
        if not path.parent.is_dir():
            raise NoteriProfileUnavailable(
                "Diretório de auditoria do modo ESTUDO não montado"
            )
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
        raise NoteriProfileInvalid(
            f"host-profile pertence a {observed}, não ao Noteri esperado"
        )


def load_profile() -> dict[str, Any]:
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
        raise NoteriProfileInvalid(f"host-profile inválido: {exc}") from exc
    if not isinstance(payload, dict):
        raise NoteriProfileInvalid("host-profile deve conter objeto JSON")
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
        raise NoteriProfileInvalid(
            "leitura independente divergiu após alteração do perfil"
        )

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
