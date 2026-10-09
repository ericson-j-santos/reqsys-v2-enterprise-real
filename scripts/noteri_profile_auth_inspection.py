"""Diagnostico HTTP somente leitura do contrato real de perfil e autenticacao DEV."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import subprocess
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

ORIGIN = "http://DESKTOP-PDQK954:8083"
PATHS = ("/api/v1/auth/config", "/api/v1/noteri/profile", "/api/runtime/health",
         "/login", "/task-console")
LIMIT = 524288
SHA_RE = re.compile(r"[0-9a-f]{40}")
CID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{7,100}")
KNOWN_KEYS = ("success", "ok", "data", "detail", "error", "message", "status",
              "mode", "service", "version", "sha", "source_sha", "routes")


class Blocked(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def summarize(path, status, content_type, raw):
    if path not in PATHS or len(raw) > LIMIT:
        raise Blocked("path_or_size_invalid")
    result = {"path": path, "http_status": status, "bytes": len(raw),
              "body_sha256": hashlib.sha256(raw).hexdigest(),
              "is_json_content_type": "application/json" in content_type.casefold(),
              "is_html_content_type": "text/html" in content_type.casefold()}
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeError):
        payload = None
    result["json_object"] = isinstance(payload, dict)
    if not isinstance(payload, dict):
        result["html_document"] = b"<html" in raw.lower() or b"<!doctype html" in raw.lower()
        return result
    result["known_root_keys"] = [key for key in KNOWN_KEYS if key in payload]
    nested = payload.get("data")
    result["data_object"] = isinstance(nested, dict)
    data = nested if isinstance(nested, dict) else payload
    for key in ("demo_login_enabled", "azure_enabled", "password_login_enabled",
                "certificate_login_enabled", "sso_enabled"):
        result[key] = data.get(key) if type(data.get(key)) is bool else None
    result["public_client_configured"] = bool(data.get("azure_client_id"))
    result["public_tenant_configured"] = bool(data.get("azure_tenant_id"))
    result["auth_status"] = data.get("auth_status") if data.get("auth_status") in (
        "ready", "disabled", "unavailable", "misconfigured", "missing_configuration") else None
    result["environment"] = data.get("environment") if data.get("environment") in (
        "dev", "development", "desenvolvimento", "local", "test",
        "stg", "hml", "production", "prod", "producao") else None
    result["profile_data_present"] = data.get("host") == "Noteri" and data.get("profile") in (
        "NORMAL", "ESTUDO")
    result["runtime_mode"] = data.get("mode") if data.get("mode") in (
        "static", "portable", "portable-dev", "native", "dev", "maintenance") else None
    result["runtime_sha"] = None
    for key in ("source_sha", "head_sha", "sha", "git_sha"):
        value = data.get(key)
        if isinstance(value, str) and SHA_RE.fullmatch(value):
            result["runtime_sha"] = value
            break
    return result


def get(path):
    if path not in PATHS:
        raise Blocked("path_not_allowlisted")
    request = Request(ORIGIN + path, headers={"Accept": "application/json, text/html",
                                             "Cache-Control": "no-store"}, method="GET")
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        response = opener.open(request, timeout=6)
    except HTTPError as error:
        response = error
    except (URLError, OSError):
        return {"path": path, "http_status": None, "state": "unreachable"}
    with response:
        status = response.code
        raw = response.read(LIMIT + 1)
        if len(raw) > LIMIT:
            return {"path": path, "http_status": status, "state": "response_too_large"}
        return summarize(path, status, response.headers.get("Content-Type", ""), raw)


def inspect(expected_sha, correlation_id, *, host=None, platform=None, sha_reader=None, fetch=get):
    if (platform or os.name) != "nt" or (host or socket.gethostname()).casefold() != "noteri":
        raise Blocked("host_not_authorized")
    if not SHA_RE.fullmatch(expected_sha) or not CID_RE.fullmatch(correlation_id):
        raise Blocked("source_or_correlation_invalid")
    if sha_reader is None:
        def sha_reader():
            result = subprocess.run(["git", "rev-parse", "HEAD"],
                                    cwd=Path(__file__).resolve().parents[1],
                                    capture_output=True, text=True, timeout=10, check=False)
            return result.stdout.strip() if result.returncode == 0 else ""
    if sha_reader() != expected_sha:
        raise Blocked("source_sha_mismatch")
    return {"inspection_completed": True, "read_only": True, "host": "Noteri",
            "source_sha": expected_sha, "correlation_id": correlation_id,
            "credentials_used": False, "profile_post_sent": False,
            "auth_configuration_changed": False, "endpoints": [fetch(path) for path in PATHS]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--correlation-id", required=True)
    args = parser.parse_args()
    try:
        result = inspect(args.expected_sha, args.correlation_id)
    except (Blocked, OSError, ValueError, subprocess.SubprocessError) as error:
        reason = str(error) if isinstance(error, Blocked) else type(error).__name__
        print(json.dumps({"inspection_completed": False, "reason": reason}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
