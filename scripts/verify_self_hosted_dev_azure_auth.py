#!/usr/bin/env python3
"""Prove real Azure authentication for the fixed isolated PC24x7 DEV API.

Only the explicitly supplied WSJF_MSAL_STORAGE_STATE_B64 is consumed. No browser
profile, cookie import, refresh token, demo login, logout or session invalidation.
An interactive Microsoft callback is a separate, unverified browser journey.
"""
from __future__ import annotations

import argparse
import base64
import binascii
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

HOST = "DESKTOP-PDQK954"
PROJECT = "reqsys-dev-selfhosted"
INSTANCE = "pc24x7-selfhost-dev-v1"
ORIGIN = "http://127.0.0.1:18080"
REDIRECT = "https://ericson-j-santos.github.io/reqsys-v2-enterprise-real/dev/auth/callback.html"
SECRET_ENV = "WSJF_MSAL_STORAGE_STATE_B64"
CONTRACT = "reqsys-self-hosted-dev-azure-auth"
CONFIRM = "VERIFY-PC24X7-DEV-AZURE-AUTH"
WORKERS = Path("C:/dev/chatgpt-workers")
REMOTE = "https://github.com/ericson-j-santos/reqsys-v2-enterprise-real.git"
SHA = re.compile(r"[0-9a-f]{40}")
GUID = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")
MAX_STATE = 2 * 1024 * 1024
MAX_TOKEN = 65536
MAX_RESPONSE = 262144
AUTH_PATHS = frozenset((
    "/api/runtime/build-info", "/api/v1/auth/config",
    "/api/v1/auth/azure", "/api/v1/auth/session",
))


class ProofError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("ascii")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProofError("duplicate_json_key")
        result[key] = value
    return result


def json_object(raw):
    try:
        value = json.loads(raw, object_pairs_hook=strict_object)
    except (ValueError, UnicodeError, TypeError):
        raise ProofError("invalid_json") from None
    if not isinstance(value, dict):
        raise ProofError("json_object_required")
    return value


def no_reparse(path):
    path = Path(path)
    for item in (path, *path.parents):
        info = item.lstat()
        if item.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ProofError("reparse_path_blocked")
    if path.is_file() and path.stat().st_nlink != 1:
        raise ProofError("hardlinked_file_blocked")


def require_host():
    if os.name != "nt" or socket.gethostname().casefold() != HOST.casefold():
        raise ProofError("fixed_windows_host_required")


def bounded_command(command, cwd, *, git=False):
    environment = os.environ.copy()
    # Child diagnostics never inherit the supplied authentication bundle.
    environment.pop(SECRET_ENV, None)
    if git:
        for name in tuple(environment):
            if name.startswith("GIT_"):
                environment.pop(name)
        environment.update({
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0",
        })
    try:
        result = subprocess.run(command, cwd=str(cwd), env=environment,
                                shell=False, capture_output=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        raise ProofError("candidate_identity_unavailable") from None
    if result.returncode or result.stderr.strip() or len(result.stdout) > 2097152:
        raise ProofError("candidate_identity_failed")
    try:
        return result.stdout.decode("utf-8").strip()
    except UnicodeError:
        raise ProofError("candidate_identity_invalid") from None


def source_context(source_sha):
    if not isinstance(source_sha, str) or not SHA.fullmatch(source_sha):
        raise ProofError("invalid_source_sha")
    require_host()
    source = WORKERS / ("rs2-" + source_sha)
    no_reparse(source)
    launcher_path = source / "scripts/verify_self_hosted_dev_azure_auth.py"
    no_reparse(launcher_path)
    if Path(__file__).resolve() != launcher_path.resolve():
        raise ProofError("fixed_source_location_required")
    def git(*args):
        return bounded_command(
            ["git", "-c", "core.longpaths=true", "-c", "core.fsmonitor=false",
             "-C", str(source), *args], source, git=True)
    if (Path(git("rev-parse", "--show-toplevel")).resolve() != source.resolve()
            or git("remote", "get-url", "origin") != REMOTE
            or git("rev-parse", "HEAD") != source_sha
            or git("status", "--porcelain", "--untracked-files=all")):
        raise ProofError("source_binding_invalid")
    records = git("ls-files", "-v").splitlines()
    if not records or any(not item.startswith("H ") for item in records):
        raise ProofError("source_index_flags_untrusted")
    if git("ls-files", "--error-unmatch", "scripts/verify_self_hosted_dev_azure_auth.py") != "scripts/verify_self_hosted_dev_azure_auth.py":
        raise ProofError("auth_proof_script_not_tracked")
    publisher_path = source / "scripts/reqsys_self_hosted_dev_publish.py"
    no_reparse(publisher_path)
    if git("ls-files", "--error-unmatch", "scripts/reqsys_self_hosted_dev_publish.py") != "scripts/reqsys_self_hosted_dev_publish.py":
        raise ProofError("publisher_not_tracked")
    spec = importlib.util.spec_from_file_location("_fixed_dev_auth_publisher", publisher_path)
    publisher = importlib.util.module_from_spec(spec)
    old = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(publisher)
    finally:
        sys.dont_write_bytecode = old
    local = os.environ.get("LOCALAPPDATA", "")
    if not local or not Path(local).is_absolute():
        raise ProofError("local_app_data_required")
    root = Path(local) / "ReqSys" / "SelfHostedDev"
    no_reparse(root)
    private = publisher.WindowsPrivateFiles()
    private.check(root)
    restore_path = root / "restore-proof.json"
    private.check(restore_path)
    raw = restore_path.read_bytes()
    if len(raw) > MAX_RESPONSE:
        raise ProofError("restore_proof_too_large")
    restore = json_object(raw)
    publisher.validate_restore_proof(
        restore, source_sha, str(restore.get("source_sha256") or ""),
        datetime.now(timezone.utc))
    return source, root, private, restore


def validate_candidate(source):
    ids = bounded_command([
        "docker", "ps", "--filter", "label=com.docker.compose.project=" + PROJECT,
        "--filter", "label=com.docker.compose.service=caddy", "--format", "{{.ID}}",
    ], source).splitlines()
    if len(ids) != 1 or not re.fullmatch(r"[0-9a-f]{12,64}", ids[0]):
        raise ProofError("candidate_gateway_not_unique")
    def inspect(field):
        return json.loads(bounded_command(
            ["docker", "inspect", "--format", "{{json " + field + "}}", ids[0]], source))
    labels, ports, running = inspect(".Config.Labels"), inspect(".NetworkSettings.Ports"), inspect(".State.Running")
    if (not isinstance(labels, dict)
            or labels.get("com.docker.compose.project") != PROJECT
            or labels.get("com.docker.compose.service") != "caddy"
            or labels.get("io.reqsys.selfhost.instance") != INSTANCE
            or running is not True):
        raise ProofError("candidate_gateway_identity_mismatch")
    bindings = ports.get("80/tcp") if isinstance(ports, dict) else None
    if (not isinstance(bindings, list) or len(bindings) != 1
            or bindings[0] != {"HostIp": "127.0.0.1", "HostPort": "18080"}):
        raise ProofError("candidate_loopback_binding_mismatch")


class RejectRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class FixedApi:
    def __init__(self):
        self.deadline = time.monotonic() + 90
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), RejectRedirect())

    def call(self, path, *, payload=None, bearer=None):
        if path not in AUTH_PATHS or (payload is not None and path != "/api/v1/auth/azure"):
            raise ProofError("api_route_not_closed")
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ProofError("authentication_deadline_exceeded")
        headers = {"Accept": "application/json", "User-Agent": "ReqSysDevAzureProof/1"}
        if bearer is not None:
            if path != "/api/v1/auth/session":
                raise ProofError("bearer_route_not_closed")
            headers["Authorization"] = "Bearer " + bearer
        body = None if payload is None else canonical(payload)
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(ORIGIN + path, data=body, headers=headers)
        try:
            with self.opener.open(request, timeout=min(12, remaining)) as response:
                status = response.status
                raw = response.read(MAX_RESPONSE + 1)
        except urllib.error.HTTPError as exc:
            status = exc.code
            exc.close()
            return status, {}
        except (OSError, urllib.error.URLError):
            raise ProofError("fixed_api_unavailable") from None
        if len(raw) > MAX_RESPONSE:
            raise ProofError("api_response_too_large")
        return status, json_object(raw)


def successful_data(status, response, code):
    if (status != 200 or response.get("success") is not True
            or response.get("errors") != []
            or not isinstance(response.get("data"), dict)):
        raise ProofError(code)
    return response["data"]


def validate_public_config(status, response):
    config = successful_data(status, response, "auth_config_not_ready")
    tenant, client = config.get("azure_tenant_id"), config.get("azure_client_id")
    if (not isinstance(tenant, str) or not GUID.fullmatch(tenant)
            or not isinstance(client, str) or not GUID.fullmatch(client)
            or config.get("azure_enabled") is not True
            or config.get("auth_status") != "ready"
            or config.get("demo_login_enabled") is not False
            or config.get("environment") != "desenvolvimento"
            or config.get("expected_redirect_uri") != REDIRECT):
        raise ProofError("auth_config_binding_invalid")
    return {key: config[key] for key in (
        "azure_tenant_id", "azure_client_id",
        "expected_redirect_uri", "demo_login_enabled")}


def jwt_parts(token):
    if not isinstance(token, str) or not 40 <= len(token) <= MAX_TOKEN:
        raise ProofError("msal_id_token_invalid")
    parts = token.split(".")
    if len(parts) != 3 or any(not re.fullmatch(r"[A-Za-z0-9_-]+", item) for item in parts):
        raise ProofError("msal_id_token_invalid")
    def decode(value):
        try:
            return base64.b64decode(value + "=" * (-len(value) % 4),
                                   altchars=b"-_", validate=True)
        except (ValueError, binascii.Error):
            raise ProofError("msal_id_token_invalid") from None
    header, claims = json_object(decode(parts[0])), json_object(decode(parts[1]))
    signature = decode(parts[2])
    if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str) or not 128 <= len(signature) <= 1024:
        raise ProofError("msal_id_token_invalid")
    return parts, claims, signature


def validate_claims(claims, public, now):
    tenant, client = public["azure_tenant_id"], public["azure_client_id"]
    if claims.get("aud") != client or claims.get("tid") != tenant:
        raise ProofError("msal_id_token_binding_invalid")
    if claims.get("iss") not in (
            "https://login.microsoftonline.com/" + tenant + "/v2.0",
            "https://sts.windows.net/" + tenant + "/"):
        raise ProofError("msal_id_token_issuer_invalid")
    if (type(claims.get("exp")) is not int or claims["exp"] <= now
            or type(claims.get("nbf")) is not int or claims["nbf"] > now
            or type(claims.get("iat")) is not int or claims["iat"] > now
            or claims["exp"] <= claims["iat"]):
        raise ProofError("msal_id_token_expired_or_future")


def supplied_id_token(encoded, public, now):
    if not encoded:
        raise ProofError("explicit_msal_state_missing")
    if not isinstance(encoded, str) or len(encoded) > (MAX_STATE * 4 // 3 + 8):
        raise ProofError("explicit_msal_state_invalid")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise ProofError("explicit_msal_state_invalid") from None
    if len(raw) > MAX_STATE:
        raise ProofError("explicit_msal_state_too_large")
    bundle = json_object(raw)
    if type(bundle.get("schemaVersion")) is not int or bundle["schemaVersion"] != 1 or not isinstance(bundle.get("sessionStorage"), list):
        raise ProofError("explicit_msal_state_schema_invalid")
    candidates = []
    # Only explicitly provided MSAL IdToken records are read. Cookies, accounts,
    # localStorage, ReqSys tokens and refresh credentials are never imported.
    for entry in bundle["sessionStorage"]:
        if (not isinstance(entry, dict) or not isinstance(entry.get("name"), str)
                or "idtoken" not in entry["name"].casefold()):
            continue
        value = entry.get("value")
        if not isinstance(value, str) or len(value) > MAX_TOKEN * 2:
            raise ProofError("msal_id_token_record_invalid")
        record = json_object(value)
        if record.get("credentialType") != "IdToken":
            raise ProofError("msal_id_token_record_invalid")
        if (record.get("clientId") == public["azure_client_id"]
                and record.get("realm") == public["azure_tenant_id"]
                and record.get("environment") in ("login.microsoftonline.com", "login.windows.net")):
            candidates.append(record.get("secret"))
    if len(candidates) != 1:
        raise ProofError("msal_id_token_not_unique_for_target")
    token = candidates[0]
    _, claims, _ = jwt_parts(token)
    validate_claims(claims, public, now)
    return token


def invalid_signature(token):
    parts, _, signature = jwt_parts(token)
    invalid = bytes([signature[0] ^ 1]) + signature[1:]
    parts[2] = base64.urlsafe_b64encode(invalid).rstrip(b"=").decode("ascii")
    return ".".join(parts)


def verify_backend(api, encoded, public, now):
    token = supplied_id_token(encoded, public, now)
    status, _ = api.call("/api/v1/auth/session")
    if status not in (401, 403):
        raise ProofError("anonymous_session_not_rejected")
    status, _ = api.call("/api/v1/auth/azure", payload={"id_token": invalid_signature(token)})
    if status != 401:
        raise ProofError("invalid_azure_signature_not_rejected")
    status, response = api.call("/api/v1/auth/azure", payload={"id_token": token})
    login = successful_data(status, response, "azure_login_not_authenticated")
    bearer = login.get("access_token")
    if (login.get("token_type") != "bearer" or not isinstance(bearer, str)
            or not 40 <= len(bearer) <= MAX_TOKEN or not isinstance(login.get("usuario"), dict)):
        raise ProofError("azure_login_token_missing")
    status, response = api.call("/api/v1/auth/session", bearer=bearer)
    session = successful_data(status, response, "api_session_not_authenticated")
    if (not isinstance(session.get("papel"), str) or not session["papel"]
            or not isinstance(session.get("permissoes"), list)
            or type(session.get("session_epoch")) is not int or session["session_epoch"] < 0
            or not isinstance(session.get("authz_version"), str)
            or not re.fullmatch(r"rbac-[0-9a-f]{16}", session["authz_version"])
            or login["usuario"].get("session_epoch") != session["session_epoch"]
            or login["usuario"].get("authz_version") != session["authz_version"]):
        raise ProofError("api_session_contract_invalid")
    return {"azure_login_status": 200, "api_session_status": 200,
            "anonymous_session_rejected": True,
            "invalid_azure_signature_rejected": True}


def make_proof(source_sha, public, restore, result, now, *, verified):
    proof = {
        "schema_version": "1", "contract": CONTRACT,
        "host": HOST, "project": PROJECT, "instance": INSTANCE,
        "source_sha": source_sha, "verified_at": now.isoformat(),
        "verification_scope": "backend_azure_session",
        "authenticated_flow_verified": verified,
        "ui_interactive_callback_verified": False,
        "demo_login_enabled": False,
        "azure_tenant_id": public["azure_tenant_id"],
        "azure_client_id": public["azure_client_id"],
        "expected_redirect_uri": public["expected_redirect_uri"],
        "auth_config_sha256": digest(public),
        "restore_proof_sha256": digest(restore),
        **result,
    }
    proof["proof_integrity_sha256"] = digest(proof)
    return proof


def execute(source_sha):
    source, root, private, restore = source_context(source_sha)
    validate_candidate(source)
    api = FixedApi()
    status, build = api.call("/api/runtime/build-info")
    if "success" in build and build["success"] is not True:
        raise ProofError("candidate_source_sha_mismatch")
    build = build.get("data", build)
    if status != 200 or not isinstance(build, dict) or build.get("build_sha") != source_sha:
        raise ProofError("candidate_source_sha_mismatch")
    status, response = api.call("/api/v1/auth/config")
    public = validate_public_config(status, response)
    result = {"azure_login_status": 0, "api_session_status": 0,
              "anonymous_session_rejected": False, "invalid_azure_signature_rejected": False}
    verified = False
    failure = None
    try:
        result = verify_backend(
            api, os.environ.get(SECRET_ENV, ""), public, int(time.time()))
        verified = True
    except ProofError as exc:
        failure = exc
    proof = make_proof(
        source_sha, public, restore, result, datetime.now(timezone.utc), verified=verified)
    # A failed authentication attempt replaces any previous positive proof for
    # this same verified candidate with a private false proof, preventing reuse.
    private.evidence(root / "auth-proof.json", canonical(proof) + b"\n")
    if failure:
        raise failure
    return {"status": "verified", "authenticated_flow_verified": True,
            "ui_interactive_callback_verified": False,
            "azure_login_status": 200, "api_session_status": 200}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--confirm", required=True, choices=(CONFIRM,))
    args = parser.parse_args(argv)
    try:
        result = execute(args.source_sha)
    except Exception as exc:
        code = exc.code if isinstance(exc, ProofError) else "authentication_proof_blocked"
        print(json.dumps({"status": "blocked", "code": code,
                          "authenticated_flow_verified": False,
                          "ui_interactive_callback_verified": False}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
