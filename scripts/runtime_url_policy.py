"""Política compartilhada para URLs de runtimes após a retirada do Fly.io."""

from __future__ import annotations

from urllib.parse import urlparse


class RuntimeURLPolicyError(ValueError):
    """URL ausente, inválida ou vinculada a um provedor aposentado."""


def require_authorized_runtime_url(value: str | None, *, label: str = "base_url") -> str:
    normalized = (value or "").strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise RuntimeURLPolicyError(f"{label} deve ser uma URL http(s) explícita")

    hostname = parsed.hostname.lower()
    if hostname in {"fly.dev", "fly.io"} or hostname.endswith((".fly.dev", ".fly.io")):
        raise RuntimeURLPolicyError(
            f"{label} aponta para Fly.io, retirado definitivamente; informe um runtime autorizado"
        )
    return normalized
