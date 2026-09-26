#!/usr/bin/env python3
"""Publica o locator assinado do runtime DEV em um tópico ntfy público.

A chave privada Ed25519 é criada no host e protegida com Windows DPAPI.
Somente URLs Quick Tunnel saudáveis, chave pública e payload assinado deixam o host.
"""
from __future__ import annotations

import base64
import json
import os
import secrets
import time
import urllib.error
import urllib.request
from pathlib import Path

import win32crypt
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
REQUIRED_PUBLIC_ENDPOINTS = (
    "/api/health",
    "/api/runtime/health",
    "/api/runtime/readiness",
    "/api/runtime/build-info",
)


def b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def b64d(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


def ensure_identity() -> tuple[Ed25519PrivateKey, dict]:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    if KEY_BLOB.is_file() and PUBLIC_CFG.is_file():
        cfg = json.loads(PUBLIC_CFG.read_text(encoding="utf-8"))
        protected = b64d(KEY_BLOB.read_text(encoding="ascii").strip())
        raw = win32crypt.CryptUnprotectData(protected, None, None, None, 0)[1]
        return Ed25519PrivateKey.from_private_bytes(raw), cfg

    key = Ed25519PrivateKey.generate()
    raw = key.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
    protected = win32crypt.CryptProtectData(
        raw,
        "ReqSys DEV locator signing key",
        None,
        None,
        None,
        0,
    )
    KEY_BLOB.write_text(b64e(protected), encoding="ascii")
    public_raw = key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    cfg = {
        "schema_version": "1.0.0",
        "topic": "reqsys-dev-locator-" + secrets.token_hex(20),
        "public_key_b64": b64e(public_raw),
    }
    PUBLIC_CFG.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return key, cfg


def probe(base_url: str, path: str) -> bool:
    try:
        request = urllib.request.Request(
            base_url.rstrip("/") + path,
            headers={"User-Agent": "ReqSysLocatorPublisher/2.0", "Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read(262_144)
            if int(response.status) != 200:
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
        with urllib.request.urlopen(request, timeout=10) as response:
            return int(response.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)
    except Exception:
        return None


def runtime_contract_ready(base_url: str) -> bool:
    return (
        all(probe(base_url, path) for path in REQUIRED_PUBLIC_ENDPOINTS)
        and probe_status(base_url, "/task-console") == 200
        and probe_status(base_url, "/@vite/client") == 404
    )


def healthy_urls() -> list[str]:
    data = json.loads(CF_STATE.read_text(encoding="utf-8"))
    urls: list[str] = []
    for tunnel in data.get("tunnels") or []:
        value = tunnel.get("url")
        if (
            value
            and value.startswith("https://")
            and value.endswith(".trycloudflare.com")
            and runtime_contract_ready(value)
        ):
            urls.append(value.rstrip("/"))
    return list(dict.fromkeys(urls))


def main() -> int:
    key, cfg = ensure_identity()
    urls = healthy_urls()
    now = int(time.time())
    payload = {
        "schema_version": "1.0.0",
        "environment": "dev",
        "issued_at": now,
        "expires_at": now + TTL_SECONDS,
        "selected_url": urls[0] if urls else None,
        "urls": urls,
        "runtime_contract": {
            "version": "2.0.0",
            "required_endpoints": list(REQUIRED_PUBLIC_ENDPOINTS),
            "static_frontend_required": True,
            "vite_hmr_forbidden": True,
        },
    }
    payload_raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    payload_b64 = b64e(payload_raw)
    envelope = json.dumps(
        {
            "v": 1,
            "payload_b64": payload_b64,
            "signature_b64": b64e(key.sign(payload_b64.encode("ascii"))),
        },
        separators=(",", ":"),
    ).encode("utf-8")

    request = urllib.request.Request(
        "https://ntfy.sh/" + cfg["topic"],
        data=envelope,
        method="POST",
        headers={
            "Content-Type": "text/plain; charset=utf-8",
            "Title": "reqsys-dev-locator",
            "Firebase": "no",
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        publish_status = int(response.status)

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
