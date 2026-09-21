#!/usr/bin/env python3
"""Publica o locator assinado do runtime DEV em um tópico ntfy público.

A chave privada Ed25519 é criada no host e protegida com Windows DPAPI.
Somente URLs Quick Tunnel saudáveis, chave pública e payload assinado deixam o host.
"""
from __future__ import annotations

import base64
import json
import os
import re
import secrets
import time
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
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


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


def _json_probe(base_url: str, path: str) -> tuple[int | None, dict]:
    try:
        request = urllib.request.Request(
            base_url.rstrip("/") + path,
            headers={
                "User-Agent": "ReqSysLocatorPublisher/2.0",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            status = int(response.status)
            payload = json.loads(response.read().decode("utf-8"))
            return status, payload if isinstance(payload, dict) else {}
    except Exception:
        return None, {}


def probe_runtime_contract(base_url: str) -> dict:
    basic_status, basic = _json_probe(base_url, "/api/health")
    runtime_status, runtime = _json_probe(base_url, "/api/runtime/health")
    build_status, build = _json_probe(base_url, "/api/runtime/build-info")
    build_data = build.get("data", build) if isinstance(build, dict) else {}
    build_sha = str(
        build_data.get("build_sha") or build_data.get("commit_sha") or ""
    ).strip().lower()
    build_sha_valid = bool(SHA_RE.fullmatch(build_sha))
    return {
        "ok": (
            basic_status == 200
            and runtime_status == 200
            and build_status == 200
            and build_sha_valid
        ),
        "basic_status": basic_status,
        "runtime_status": runtime_status,
        "build_status": build_status,
        "build_sha": build_sha if build_sha_valid else None,
        "basic_success": basic.get("success") is True if basic else False,
        "runtime_success": runtime.get("success") is True if runtime else False,
    }


def healthy_urls() -> tuple[list[str], dict[str, dict]]:
    data = json.loads(CF_STATE.read_text(encoding="utf-8"))
    urls: list[str] = []
    evidence: dict[str, dict] = {}
    for tunnel in data.get("tunnels") or []:
        value = tunnel.get("url")
        if not (
            value
            and value.startswith("https://")
            and value.endswith(".trycloudflare.com")
        ):
            continue
        normalized = value.rstrip("/")
        contract = probe_runtime_contract(normalized)
        evidence[normalized] = contract
        if contract.get("ok") is True:
            urls.append(normalized)
    return list(dict.fromkeys(urls)), evidence


def main() -> int:
    key, cfg = ensure_identity()
    urls, runtime_evidence = healthy_urls()
    now = int(time.time())
    if not urls:
        result = {
            "published": False,
            "publish_status": None,
            "healthy_url_count": 0,
            "selected_url": None,
            "expires_at": None,
            "topic": cfg["topic"],
            "public_key_b64": cfg["public_key_b64"],
            "reason": "runtime_contract_not_proven",
            "runtime_contract": runtime_evidence,
        }
        PUBLISH_STATE.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
        return 2

    selected_build_sha = runtime_evidence[urls[0]].get("build_sha")
    payload = {
        "schema_version": "1.0.0",
        "environment": "dev",
        "issued_at": now,
        "expires_at": now + TTL_SECONDS,
        "selected_url": urls[0],
        "urls": urls,
        "runtime_build_sha": selected_build_sha,
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
        "runtime_build_sha": selected_build_sha,
        "runtime_contract_proven": True,
    }
    PUBLISH_STATE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if result["published"] and result["runtime_contract_proven"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
