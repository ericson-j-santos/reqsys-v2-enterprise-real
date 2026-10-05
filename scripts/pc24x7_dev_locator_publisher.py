#!/usr/bin/env python3
"""Publica o locator assinado do runtime DEV em um tópico ntfy público.

A chave privada Ed25519 é provisionada no host e protegida com Windows DPAPI.
Somente URLs Quick Tunnel saudáveis, chave pública e payload assinado deixam o host.
"""
from __future__ import annotations

import argparse
import importlib.util
import base64
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

def _load_maintenance_module():
    try:
        from scripts import self_hosted_dev_maintenance
        return self_hosted_dev_maintenance
    except (ImportError, ModuleNotFoundError):
        module_path = Path(__file__).resolve().with_name("self_hosted_dev_maintenance.py")
        spec = importlib.util.spec_from_file_location("self_hosted_dev_maintenance", module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("self_hosted_dev_maintenance_loader_unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


portable_dev = _load_maintenance_module()

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

BASE = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "ReqSys"
RUNTIME = BASE / "RuntimeSupervisor"
PUBLIC = BASE / "PublicRuntime"
CF_STATE = PUBLIC / "dev-tunnels.json"
KEY_BLOB = RUNTIME / "dev-locator-key.dpapi"
PUBLIC_CFG = RUNTIME / "dev-locator-public.json"
PUBLISH_STATE = PUBLIC / "dev-locator-publish.json"
TTL_SECONDS = 900
MAX_RELAY_ENVELOPE_BYTES = 16_384
LOCATOR_TITLE = "reqsys-dev-locator"
PINNED_TOPIC = "reqsys-dev-locator-1651e9182d6e1c939fa6672c1248c9d532716fe7"
PINNED_PUBLIC_KEY_B64 = "Ox1kIxgrkNTG96NI69Obi/W+ZiZz2jxw3DLCQMvwMcM="
REQUIRED_PUBLIC_ENDPOINTS = (
    "/api/health",
    "/api/runtime/health",
    "/api/runtime/readiness",
    "/api/runtime/build-info",
)
CRITICAL_ROUTE_PROBES = (
    ("/v1/cofre/runtime/control-status", frozenset({401, 403})),
    ("/v1/teams-gateway/flow-bot/owners", frozenset({401, 403})),
)


class RejectRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        del req, fp, code, msg, headers, newurl
        return None


NO_REDIRECT_OPENER = urllib.request.build_opener(RejectRedirectHandler())


def open_no_redirect(request: urllib.request.Request, *, timeout: int):
    return NO_REDIRECT_OPENER.open(request, timeout=timeout)


def b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def b64d(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


def public_identity(key: Ed25519PrivateKey) -> str:
    public_raw = key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    return b64e(public_raw)


def validate_pinned_identity(
    key: Ed25519PrivateKey,
    cfg: dict,
) -> tuple[Ed25519PrivateKey, dict]:
    if not isinstance(cfg, dict):
        raise RuntimeError("locator_public_config_invalid")
    if not hmac.compare_digest(str(cfg.get("topic") or ""), PINNED_TOPIC):
        raise RuntimeError("locator_topic_not_pinned")
    if not hmac.compare_digest(
        str(cfg.get("public_key_b64") or ""),
        PINNED_PUBLIC_KEY_B64,
    ):
        raise RuntimeError("locator_public_key_config_not_pinned")
    if not hmac.compare_digest(public_identity(key), PINNED_PUBLIC_KEY_B64):
        raise RuntimeError("locator_private_key_does_not_match_pinned_public_key")
    return key, cfg


def ensure_identity() -> tuple[Ed25519PrivateKey, dict]:
    if KEY_BLOB.is_file() != PUBLIC_CFG.is_file():
        raise RuntimeError("locator_identity_partial_state")
    if not KEY_BLOB.is_file():
        raise RuntimeError("pinned_locator_identity_missing")
    if os.name != "nt":
        raise RuntimeError("windows_dpapi_required")
    import win32crypt

    cfg = json.loads(PUBLIC_CFG.read_text(encoding="utf-8"))
    protected = b64d(KEY_BLOB.read_text(encoding="ascii").strip())
    raw = win32crypt.CryptUnprotectData(protected, None, None, None, 0)[1]
    key = Ed25519PrivateKey.from_private_bytes(raw)
    return validate_pinned_identity(key, cfg)


def probe(base_url: str, path: str) -> bool:
    try:
        request = urllib.request.Request(
            base_url.rstrip("/") + path,
            headers={"User-Agent": "ReqSysLocatorPublisher/2.0", "Accept": "application/json"},
        )
        with open_no_redirect(request, timeout=15) as response:
            body = response.read(262_145)
            if int(response.status) != 200:
                return False
            if len(body) > 262_144:
                return False
            if path.startswith("/api/"):
                payload = json.loads(body.decode("utf-8"))
                if not isinstance(payload, dict):
                    return False
            return True
    except Exception:
        return False


def probe_status(base_url: str, path: str) -> int | None:
    try:
        request = urllib.request.Request(
            base_url.rstrip("/") + path,
            headers={"User-Agent": "ReqSysLocatorPublisher/3.0", "Accept": "*/*"},
        )
        with open_no_redirect(request, timeout=15) as response:
            return int(response.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)
    except Exception:
        return None


def critical_route_ready(base_url: str, path: str, expected_statuses: frozenset[int]) -> bool:
    """Prova que uma rota crítica chega ao backend sem usar credenciais.

    401/403 são sucesso de contrato para superfícies autenticadas: comprovam que
    o request não caiu no frontend/Nginx legado. 404/405/2xx inesperado falham.
    """
    status = probe_status(base_url, path)
    return status in expected_statuses


def static_frontend_ready(base_url: str) -> bool:
    try:
        request = urllib.request.Request(
            base_url.rstrip("/") + "/task-console",
            headers={
                "User-Agent": "ReqSysLocatorPublisher/3.0",
                "Accept": "text/html",
            },
        )
        with open_no_redirect(request, timeout=15) as response:
            body = response.read(524_289)
            content_type = str(response.headers.get("Content-Type") or "").lower()
            if int(response.status) != 200 or len(body) > 524_288:
                return False
            if "text/html" not in content_type:
                return False
            html = body.decode("utf-8", errors="strict")
            return "/assets/" in html and "/src/main.js" not in html
    except Exception:
        return False


def runtime_contract_ready(base_url: str) -> bool:
    return (
        all(probe(base_url, path) for path in REQUIRED_PUBLIC_ENDPOINTS)
        and all(critical_route_ready(base_url, path, statuses) for path, statuses in CRITICAL_ROUTE_PROBES)
        and static_frontend_ready(base_url)
        and probe_status(base_url, "/@vite/client") == 404
    )


def healthy_urls() -> list[str]:
    data = json.loads(CF_STATE.read_text(encoding="utf-8"))
    urls: list[str] = []
    for tunnel in data.get("tunnels") or []:
        value = tunnel.get("url")
        if not isinstance(value, str):
            continue
        normalized = value.rstrip("/")
        if allowed_runtime_url(normalized) and runtime_contract_ready(normalized):
            urls.append(normalized)
    return list(dict.fromkeys(urls))


def allowed_runtime_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
    except (TypeError, ValueError):
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname is not None
        and parsed.hostname.endswith(".trycloudflare.com")
        and parsed.username is None
        and parsed.password is None
        and parsed.port is None
        and parsed.path in ("", "/")
        and not parsed.query
        and not parsed.fragment
    )


def build_payload(urls: list[str], *, now_epoch: int | None = None) -> dict:
    normalized = list(dict.fromkeys(value.rstrip("/") for value in urls))
    if not normalized:
        raise ValueError("no_healthy_runtime_urls")
    if not all(allowed_runtime_url(value) for value in normalized):
        raise ValueError("invalid_runtime_url")
    now = int(time.time()) if now_epoch is None else int(now_epoch)
    return {
        "schema_version": "1.0.0",
        "environment": "dev",
        "issued_at": now,
        "expires_at": now + TTL_SECONDS,
        "selected_url": normalized[0],
        "urls": normalized,
        "runtime_contract": {
            "version": "2.0.0",
            "required_endpoints": list(REQUIRED_PUBLIC_ENDPOINTS),
            "critical_route_probes": [
                {"path": path, "expected_statuses": sorted(statuses)}
                for path, statuses in CRITICAL_ROUTE_PROBES
            ],
            "static_frontend_required": True,
            "vite_hmr_forbidden": True,
        },
    }


def sign_payload(payload: dict, key: Ed25519PrivateKey) -> bytes:
    payload_raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    payload_b64 = b64e(payload_raw)
    return json.dumps(
        {
            "v": 1,
            "payload_b64": payload_b64,
            "signature_b64": b64e(key.sign(payload_b64.encode("ascii"))),
        },
        separators=(",", ":"),
    ).encode("utf-8")


def publish_envelope(topic: str, envelope: bytes) -> int:
    if not hmac.compare_digest(topic, PINNED_TOPIC):
        raise ValueError("invalid_locator_topic")

    request = urllib.request.Request(
        "https://ntfy.sh/" + topic,
        data=envelope,
        method="POST",
        headers={
            "Content-Type": "text/plain; charset=utf-8",
            "Title": LOCATOR_TITLE,
            "Firebase": "no",
        },
    )
    with open_no_redirect(request, timeout=15) as response:
        return int(response.status)


def write_sign_only_envelope(path: Path, envelope: bytes) -> str:
    if not envelope or len(envelope) > MAX_RELAY_ENVELOPE_BYTES:
        raise ValueError("relay_envelope_size_invalid")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(envelope)
    return hashlib.sha256(envelope).hexdigest()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publica ou assina o locator DEV")
    parser.add_argument(
        "--sign-only",
        action="store_true",
        help="gera envelope público para relay, sem publicar no ntfy",
    )
    parser.add_argument(
        "--envelope-output",
        type=Path,
        help="arquivo temporário que recebe somente o envelope público assinado",
    )
    args = parser.parse_args(argv)
    if args.sign_only != bool(args.envelope_output):
        parser.error("--sign-only e --envelope-output devem ser usados juntos")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        portable = portable_dev.control_if_active(
            publish=True, sign_only_output=args.envelope_output if args.sign_only else None)
    except portable_dev.PortableRuntimeError as exc:
        print(json.dumps({"published": False, "usable": False,
                          "runtime_provider": "self_hosted_dev",
                          "error": exc.code, "legacy_runtime_touched": False}, sort_keys=True))
        return 2
    if portable is not None:
        print(json.dumps({**portable, "candidate_locator_publication_deferred": False}, sort_keys=True))
        return 0
    key, cfg = ensure_identity()
    urls = healthy_urls()
    if args.sign_only and not urls:
        print(json.dumps({
            "signed": False,
            "relay_ready": False,
            "reason": "no_healthy_runtime_urls",
            "environment": "dev",
            "production_touched": False,
            "secrets_exported": False,
        }, ensure_ascii=True, sort_keys=True))
        return 2

    payload = build_payload(urls, now_epoch=int(time.time()))
    envelope = sign_payload(payload, key)

    if args.sign_only:
        envelope_sha256 = write_sign_only_envelope(args.envelope_output, envelope)
        print(json.dumps({
            "signed": True,
            "relay_ready": True,
            "environment": "dev",
            "healthy_url_count": len(urls),
            "selected_url": payload["selected_url"],
            "issued_at": payload["issued_at"],
            "expires_at": payload["expires_at"],
            "envelope_sha256": envelope_sha256,
            "production_touched": False,
            "secrets_exported": False,
            "published": False,
        }, ensure_ascii=True, sort_keys=True))
        return 0

    publish_status = publish_envelope(cfg["topic"], envelope)

    result = {
        "published": publish_status == 200,
        "publish_status": publish_status,
        "healthy_url_count": len(urls),
        "selected_url": payload["selected_url"],
        "expires_at": payload["expires_at"],
        "topic": cfg["topic"],
        "public_key_b64": cfg["public_key_b64"],
        "required_public_endpoints": list(REQUIRED_PUBLIC_ENDPOINTS),
        "runtime_contract_required": True,
        "static_frontend_required": True,
        "vite_hmr_forbidden": True,
    }
    PUBLISH_STATE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if result["published"] and urls else 2


if __name__ == "__main__":
    raise SystemExit(main())
