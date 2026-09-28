#!/usr/bin/env python3
"""Resolve o runtime público DEV canônico sem fallback para Fly.io.

Reutiliza o resolvedor Ed25519 versionado em `resolve_pc24x7_dev_locator.mjs`.
A URL resultante precisa ser HTTPS, sem credenciais/porta e terminar em
`.trycloudflare.com`. Nenhum URL legado é aceito como fallback.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
RESOLVER = ROOT / "scripts" / "resolve_pc24x7_dev_locator.mjs"
STABLE_DEV_ENTRYPOINT = "https://ericson-j-santos.github.io/reqsys-v2-enterprise-real/dev/"
FORBIDDEN_DEV_HOSTS = frozenset({"reqsys-app-dev.fly.dev", "reqsys-api-dev.fly.dev"})


class DevRuntimeResolutionError(RuntimeError):
    pass


def validate_runtime_base(value: str) -> str:
    raw = str(value or "").strip().rstrip("/")
    try:
        parsed = urlparse(raw)
    except ValueError as exc:
        raise DevRuntimeResolutionError("dev_runtime_url_invalid") from exc
    host = (parsed.hostname or "").casefold()
    if (
        parsed.scheme != "https"
        or not host.endswith(".trycloudflare.com")
        or host in FORBIDDEN_DEV_HOSTS
        or parsed.username
        or parsed.password
        or parsed.port
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise DevRuntimeResolutionError("dev_runtime_url_not_allowlisted")
    return raw


def resolve_signed_dev_runtime(
    *,
    repo_root: Path | None = None,
    timeout_seconds: float = 30.0,
    run_fn: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    root = (repo_root or ROOT).resolve()
    resolver = root / "scripts" / "resolve_pc24x7_dev_locator.mjs"
    if not resolver.is_file():
        raise DevRuntimeResolutionError("signed_locator_resolver_missing")
    if timeout_seconds <= 0 or timeout_seconds > 120:
        raise DevRuntimeResolutionError("signed_locator_timeout_invalid")

    with tempfile.TemporaryDirectory(prefix="reqsys-dev-locator-") as temp:
        output = Path(temp) / "locator.json"
        try:
            completed = run_fn(
                ["node", str(resolver), "--output", str(output)],
                cwd=root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DevRuntimeResolutionError("signed_locator_resolution_unavailable") from exc

        if completed.returncode != 0:
            raise DevRuntimeResolutionError(
                f"signed_locator_resolution_failed_exit_{completed.returncode}"
            )
        if not output.is_file():
            raise DevRuntimeResolutionError("signed_locator_evidence_missing")
        try:
            payload = json.loads(output.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DevRuntimeResolutionError("signed_locator_evidence_invalid") from exc

    if (
        payload.get("contract") != "reqsys-pc24x7-dev-signed-locator-resolution"
        or payload.get("signature_verified") is not True
        or payload.get("environment") != "dev"
        or payload.get("locator_transport") != "ntfy_signed_ed25519"
    ):
        raise DevRuntimeResolutionError("signed_locator_contract_invalid")

    selected = validate_runtime_base(str(payload.get("selected_url") or ""))
    runtime_contract = payload.get("runtime_contract")
    if not isinstance(runtime_contract, dict) or runtime_contract.get("version") != "2.0.0":
        raise DevRuntimeResolutionError("signed_locator_runtime_contract_invalid")
    required = runtime_contract.get("required_endpoints")
    mandatory = {
        "/api/health",
        "/api/runtime/health",
        "/api/runtime/readiness",
        "/api/runtime/build-info",
    }
    if not isinstance(required, list) or not mandatory.issubset(set(required)):
        raise DevRuntimeResolutionError("signed_locator_required_endpoints_missing")

    return {
        "base_url": selected,
        "stable_entrypoint": STABLE_DEV_ENTRYPOINT,
        "signature_verified": True,
        "locator_transport": "ntfy_signed_ed25519",
        "runtime_contract_version": "2.0.0",
        "required_endpoints": list(required),
    }


def same_origin_api_base(runtime_base: str) -> str:
    return validate_runtime_base(runtime_base) + "/api"


def build_dev_targets(runtime_base: str) -> dict[str, str]:
    base = validate_runtime_base(runtime_base)
    return {
        "frontend": base + "/",
        "health": base + "/api/health",
        "runtime_health": base + "/api/runtime/health",
        "readiness": base + "/api/runtime/readiness",
        "liveness": base + "/api/runtime/liveness",
        "build_info": base + "/api/runtime/build-info",
        "api_docs": base + "/api/docs",
        "auth_config": base + "/api/v1/auth/config",
    }
