#!/usr/bin/env python3
"""Leitor somente GET de evidências originais em duas autoridades externas mTLS.

Não emite witness, não ativa runner e não habilita trabalho. Testes usam readers
falsos explicitamente; prova física exige fontes reais homologadas fora do host.
"""
from __future__ import annotations

import json
import re
import ssl
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPSHandler, HTTPRedirectHandler, Request, build_opener

from scripts.reqsys_native_independent_issuer import AUDIT_FIELDS, CHECKPOINT_FIELDS
from scripts.validate_reqsys_native_dev_profile import NativeAdmissionBlocked

SOURCE_AUDIT = "trusted-independent-command-gateway-audit-v1"
SOURCE_CAS = "trusted-independent-cas-readback-v1"
TAG = "reqsys-native-dev-readonly-probe"
MAX_BYTES = 65536


def require(condition: bool, code: str) -> None:
    if not condition:
        raise NativeAdmissionBlocked(code)


def origin_checked(origin: str) -> str:
    require(isinstance(origin, str), "external_origin_unconfigured")
    try:
        p = urlsplit(origin)
        host = p.hostname
        port = p.port
    except ValueError:
        raise NativeAdmissionBlocked("external_origin_invalid") from None
    require(p.scheme == "https" and isinstance(host, str)
            and "." in host and host != "localhost"
            and p.netloc == host and port is None
            and not (p.path or p.query or p.fragment or p.username or p.password),
            "external_origin_invalid")
    return origin


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int,
                         msg: str, headers: Any, newurl: str) -> None:
        return None


class MTLSReader:
    """Usar APENAS no observador externo com material de confiança protegido."""

    def __init__(self, *, origin: str, ca: Path, client_cert: Path, client_key: Path):
        self.origin = origin_checked(origin)
        for file in (ca, client_cert, client_key):
            require(isinstance(file, Path) and file.is_absolute()
                    and file.is_file() and not file.is_symlink(),
                    "external_tls_unprovisioned")
        try:
            ctx = ssl.create_default_context(cafile=str(ca))
            ctx.load_cert_chain(certfile=str(client_cert), keyfile=str(client_key))
        except (ValueError, OSError, ssl.SSLError):
            raise NativeAdmissionBlocked("external_tls_unprovisioned") from None
        require(ctx.check_hostname and ctx.verify_mode == ssl.CERT_REQUIRED,
                "external_tls_not_verified")
        self.opener = build_opener(HTTPSHandler(context=ctx), _NoRedirect())

    def get(self, resource: str) -> dict[str, Any]:
        require(isinstance(resource, str) and (
            re.fullmatch(r"/v1/gateway/audit/events/native-[a-z0-9-]{14,90}", resource)
            or re.fullmatch(r"/v1/cas/checkpoints/[0-9a-f]{64}", resource)),
            "external_resource_forbidden")
        req = Request(self.origin + resource, method="GET",
                      headers={"Accept": "application/json"})
        try:
            with self.opener.open(req, timeout=5) as response:
                require(response.status == 200, "external_http_invalid")
                require(response.headers.get_content_type() == "application/json",
                        "external_media_type_invalid")
                data = response.read(MAX_BYTES + 1)
        except (HTTPError, URLError, TimeoutError, OSError):
            raise NativeAdmissionBlocked("external_source_unavailable") from None
        require(len(data) <= MAX_BYTES, "external_payload_oversized")
        try:
            value = json.loads(data.decode("utf-8"))
        except (ValueError, UnicodeError):
            raise NativeAdmissionBlocked("external_payload_invalid") from None
        require(type(value) is dict, "external_payload_invalid")
        return value


def read_original_sources(*, audit_origin: str, cas_origin: str,
                          audit_get: Callable[[str], dict[str, Any]],
                          cas_get: Callable[[str], dict[str, Any]],
                          event_id: str, source_sha: str, physical_host_id: str,
                          session_id: str, correlation_id: str, lease_id: str,
                          checkpoint_sha256: str) -> dict[str, Any]:
    """Os readers só são confiáveis se fornecidos por MTLSReader do controlador.

    Injeção de funções é permitida em teste unitário, NUNCA como atestado físico.
    """
    require(origin_checked(audit_origin) != origin_checked(cas_origin),
            "external_origins_not_independent")
    require(isinstance(event_id, str) and
            re.fullmatch(r"native-[a-z0-9-]{14,90}", event_id) is not None,
            "external_event_invalid")
    require(isinstance(source_sha, str) and
            re.fullmatch(r"[a-f0-9]{40}", source_sha) is not None,
            "external_sha_invalid")
    require(isinstance(checkpoint_sha256, str) and
            re.fullmatch(r"[a-f0-9]{64}", checkpoint_sha256) is not None,
            "external_checkpoint_invalid")
    require(isinstance(physical_host_id, str) and
            re.fullmatch(r"host-[a-z0-9-]{8,80}", physical_host_id) is not None,
            "external_host_invalid")
    require(all(isinstance(x, str) and len(x) >= 12
                for x in (session_id, correlation_id, lease_id)),
            "external_session_invalid")
    try:
        audit = audit_get("/v1/gateway/audit/events/" + event_id)
        cas = cas_get("/v1/cas/checkpoints/" + checkpoint_sha256)
    except NativeAdmissionBlocked:
        raise
    except Exception:
        raise NativeAdmissionBlocked("external_source_unavailable") from None
    require(type(audit) is dict and set(audit) == AUDIT_FIELDS,
            "external_audit_fields_invalid")
    require(audit == {
        "schema_version": 1, "source": SOURCE_AUDIT,
        "event_id": event_id, "source_sha": source_sha,
        "session_id": session_id, "correlation_id": correlation_id,
        "command_tag": TAG, "result": "ok",
        "gateway_exit_code": 0, "state_changed": False,
    }, "external_audit_mismatch")
    require(type(cas) is dict and set(cas) == CHECKPOINT_FIELDS,
            "external_cas_fields_invalid")
    require(cas == {
        "schema_version": 1, "source": SOURCE_CAS,
        "event_id": event_id, "source_sha": source_sha,
        "physical_host_id": physical_host_id, "lease_id": lease_id,
        "checkpoint_sha256": checkpoint_sha256,
        "lease_exclusive": True, "state_validated": True,
    }, "external_cas_lease_mismatch")
    return {"status": "EXTERNAL_READBACK_ONLY", "gateway_audit": audit,
            "checkpoint_readback": cas, "ready_for_work": False,
            "dispatch_allowed": False, "continuity_certified": False}
