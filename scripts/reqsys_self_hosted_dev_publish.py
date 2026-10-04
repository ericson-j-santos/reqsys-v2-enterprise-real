#!/usr/bin/env python3
"""Prepara/publica Compose DEV isolado, chamado pelo Command Gateway."""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wintypes
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import time
import urllib.request

HOST = "DESKTOP-PDQK954"
REPOSITORY = "ericson-j-santos/reqsys-v2-enterprise-real"
PROJECT = "reqsys-dev-selfhosted"
INSTANCE = "pc24x7-selfhost-dev-v1"
LOCAL_HEALTH_ORIGIN = "http://localhost:18080"
PAGES_UI_ORIGIN = "https://ericson-j-santos.github.io"
PAGES_UI_URL = PAGES_UI_ORIGIN + "/reqsys-v2-enterprise-real/dev"
SHA = re.compile(r"[0-9a-f]{40}")
DIGEST = re.compile(r"[0-9a-f]{64}")
TABLE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,62}")
MAX_PROOF_AGE = 3600
SERVICES = ("db", "redis", "api", "frontend", "gateway", "caddy")


class PublishError(RuntimeError):
    def __init__(self, code: str):
        self.code = code if re.fullmatch(r"[a-z0-9_]+", code) else "publish_operation_failed"
        super().__init__(self.code)


def require_host() -> None:
    if os.name != "nt" or socket.gethostname().casefold() != HOST.casefold():
        raise PublishError("fixed_windows_host_required")


def validate_sha(value: str) -> str:
    if not SHA.fullmatch(value):
        raise PublishError("invalid_source_sha")
    return value


def no_reparse(path: Path) -> None:
    info = path.lstat()
    if path.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
        raise PublishError("reparse_path_blocked")
    if path.is_file() and info.st_nlink != 1:
        raise PublishError("hardlinked_file_blocked")


class WindowsPrivateFiles:
    """DACL protegida: somente usuário atual e SYSTEM; sem shell."""

    def __init__(self):
        if os.name != "nt":
            raise PublishError("windows_acl_required")
        self.adv = ctypes.WinDLL("advapi32", use_last_error=True)
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.GetCurrentProcess.restype = wintypes.HANDLE
        self.kernel.LocalFree.argtypes = [ctypes.c_void_p]
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.adv.OpenProcessToken.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)
        ]
        self.adv.GetTokenInformation.argtypes = [
            wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
            wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)
        ]
        self.adv.ConvertSidToStringSidW.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)
        ]
        self.adv.ConvertStringSidToSidW.argtypes = [
            wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p)
        ]
        self.adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD,
            ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.DWORD)
        ]
        self.adv.SetFileSecurityW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p
        ]
        self.adv.GetFileSecurityW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p,
            wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)
        ]
        self.adv.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [
            ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
            ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.DWORD)
        ]
        self.sid = self._user_sid()
        self.sddl = f"D:P(A;;FA;;;{self.sid})(A;;FA;;;SY)"
        self.directory_sddl = f"D:P(A;OICI;FA;;;{self.sid})(A;OICI;FA;;;SY)"

    def _canonical_sid(self, value: str) -> str:
        """Compara SID real, independentemente do alias usado pelo SDDL."""
        sid = ctypes.c_void_p()
        if not self.adv.ConvertStringSidToSidW(value, ctypes.byref(sid)):
            raise PublishError("private_acl_sid_invalid")
        text = ctypes.c_void_p()
        try:
            if not self.adv.ConvertSidToStringSidW(sid, ctypes.byref(text)):
                raise PublishError("private_acl_sid_invalid")
            try:
                return ctypes.wstring_at(text)
            finally:
                self.kernel.LocalFree(text)
        finally:
            self.kernel.LocalFree(sid)

    def _user_sid(self) -> str:
        token = wintypes.HANDLE()
        if not self.adv.OpenProcessToken(
            self.kernel.GetCurrentProcess(), 8, ctypes.byref(token)
        ):
            raise PublishError("private_acl_identity_failed")
        try:
            size = wintypes.DWORD()
            self.adv.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
            buffer = ctypes.create_string_buffer(size.value)
            if not self.adv.GetTokenInformation(
                token, 1, buffer, size.value, ctypes.byref(size)
            ):
                raise PublishError("private_acl_identity_failed")
            sid = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p)).contents.value
            text = ctypes.c_void_p()
            if not self.adv.ConvertSidToStringSidW(sid, ctypes.byref(text)):
                raise PublishError("private_acl_identity_failed")
            try:
                return ctypes.wstring_at(text)
            finally:
                self.kernel.LocalFree(text)
        finally:
            self.kernel.CloseHandle(token)

    def secure(self, path: Path) -> None:
        no_reparse(path)
        descriptor = ctypes.c_void_p()
        if not self.adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            self.directory_sddl if path.is_dir() else self.sddl,
            1, ctypes.byref(descriptor), None
        ):
            raise PublishError("private_acl_descriptor_failed")
        try:
            if not self.adv.SetFileSecurityW(
                str(path), 0x80000004, descriptor
            ):
                raise PublishError("private_acl_write_failed")
        finally:
            self.kernel.LocalFree(descriptor)
        self.check(path)

    def check(self, path: Path) -> None:
        no_reparse(path)
        size = wintypes.DWORD()
        self.adv.GetFileSecurityW(str(path), 4, None, 0, ctypes.byref(size))
        if not size.value:
            raise PublishError("private_acl_read_failed")
        descriptor = ctypes.create_string_buffer(size.value)
        if not self.adv.GetFileSecurityW(
            str(path), 4, descriptor, size.value, ctypes.byref(size)
        ):
            raise PublishError("private_acl_read_failed")
        text = ctypes.c_void_p()
        if not self.adv.ConvertSecurityDescriptorToStringSecurityDescriptorW(
            descriptor, 1, 4, ctypes.byref(text), None
        ):
            raise PublishError("private_acl_read_failed")
        try:
            value = ctypes.wstring_at(text)
        finally:
            self.kernel.LocalFree(text)
        flags = r"(?:OICI)?" if path.is_dir() else ""
        match = re.fullmatch(r"D:P(?:AI)?((?:\(A;" + flags + r";FA;;;[^)]+\)){2})", value)
        if not match:
            raise PublishError("private_acl_not_exclusive")
        identities = re.findall(r"\(A;" + flags + r";FA;;;([^)]+)\)", match.group(1))
        normalized = [self._canonical_sid(identity) for identity in identities]
        expected = (self._canonical_sid(self.sid), self._canonical_sid("SY"))
        if sorted(normalized) != sorted(expected):
            raise PublishError("private_acl_not_exclusive")

    def directory(self, path: Path) -> None:
        if path.exists():
            self.check(path)
            return
        path.mkdir()
        # Nenhum segredo existe antes da DACL ser aplicada e verificada.
        self.secure(path)

    def create(self, path: Path, content: bytes) -> None:
        self.check(path.parent)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            self.secure(path)
            with os.fdopen(fd, "wb") as stream:
                fd = -1
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            if fd != -1:
                os.close(fd)

    def preserving(self, path: Path, content: bytes) -> None:
        if path.exists():
            self.check(path)
            if path.read_bytes() != content:
                raise PublishError("existing_configuration_mismatch")
            return
        self.create(path, content)

    def evidence(self, path: Path, content: bytes) -> None:
        if path.exists():
            self.check(path)
        temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
        try:
            self.create(temporary, content)
            os.replace(temporary, path)
            self.check(path)
        finally:
            if temporary.exists():
                temporary.unlink()


def initialize_secrets(root: Path, private: WindowsPrivateFiles,
                       create_jwt: bool = True) -> list[str]:
    created = []
    private.directory(root)
    if not create_jwt and not (root / "jwt_secret").is_file():
        raise PublishError("original_jwt_secret_required")
    for name in ("db_owner_password", "db_app_password", "jwt_secret"):
        path = root / name
        if path.exists():
            private.check(path)
            raw = path.read_bytes()
            if name == "jwt_secret":
                try:
                    value = raw.decode("utf-8")
                except UnicodeError as exc:
                    raise PublishError("existing_secret_invalid") from exc
                if not value or len(raw) > 65536 or "\x00" in value:
                    raise PublishError("existing_secret_invalid")
            elif not DIGEST.fullmatch(raw.decode("utf-8").strip()):
                raise PublishError("existing_secret_invalid")
            continue
        private.create(path, (secrets.token_hex(32) + "\n").encode("ascii"))
        created.append(name)
    return created


class RejectRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def get_json(url: str, timeout: int = 8) -> dict:
    request = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": "ReqSysDevPublish/1"}
    )
    with urllib.request.build_opener(RejectRedirect()).open(
        request, timeout=timeout
    ) as response:
        if response.status != 200:
            raise PublishError("probe_http_status_invalid")
        raw = response.read(65537)
    if len(raw) > 65536:
        raise PublishError("probe_payload_too_large")
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise PublishError("probe_payload_invalid")
    if result.get("success") is False or result.get("error") or result.get("errors"):
        raise PublishError("probe_response_reported_failure")
    if "data" in result and (
            result.get("success") is not True or result.get("errors") != []):
        raise PublishError("probe_envelope_invalid")
    data = result.get("data", result)
    if not isinstance(data, dict):
        raise PublishError("probe_payload_invalid")
    return data


def validate_health_payload(endpoint: str, data: dict) -> None:
    """Same health semantics as the portable runtime gate, without its marker."""
    if not isinstance(data, dict) or data.get("service") != "reqsys-api":
        raise PublishError("published_health_service_invalid")
    for flag in ("ready", "healthy", "available", "database_ok"):
        if flag in data and data[flag] is not True:
            raise PublishError("published_health_negative_flag")
    checks = data.get("checks")
    if checks is not None:
        if not isinstance(checks, dict) or not checks:
            raise PublishError("published_health_checks_invalid")
        if any(value is not True and value not in ("ok", "healthy", "ready", "available")
               for value in checks.values()):
            raise PublishError("published_health_check_failed")
    if endpoint == "/api/health":
        database = data.get("database")
        if (data.get("status") != "ok" or not isinstance(database, dict)
                or database.get("status") != "ok"):
            raise PublishError("published_database_health_failed")
    elif endpoint in ("/api/runtime/health", "/api/runtime/readiness"):
        expected_status, expected_check = (
            ("ok", "health") if endpoint.endswith("/health") else ("ready", "readiness")
        )
        if (data.get("schema_version") != "1.1.0"
                or data.get("environment") != "desenvolvimento"
                or data.get("status") != expected_status or data.get("check") != expected_check):
            raise PublishError("published_runtime_health_invalid")
    elif endpoint == "/api/runtime/build-info":
        if data.get("environment") != "desenvolvimento":
            raise PublishError("published_build_environment_invalid")
    else:
        raise PublishError("published_health_endpoint_invalid")


def discover_public_ids() -> tuple[str, str]:
    try:
        config = get_json("http://127.0.0.1:8083/api/v1/auth/config")
        values = tuple(str(config.get(k) or "").strip() for k in (
            "azure_tenant_id", "azure_client_id"
        ))
        if all(re.fullmatch(
            r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", v
        ) for v in values):
            return values
    except (OSError, ValueError, PublishError):
        # Descoberta opcional: IDs vazios mantêm a publicação em modo fail-closed.
        pass
    return "", ""


def render_config(secret_root: Path, ids: tuple[str, str]) -> bytes:
    root = secret_root.as_posix()
    if not re.fullmatch(r"[A-Za-z0-9:/ _.~\-]+", root):
        raise PublishError("private_path_not_representable")
    values = {
        "COMPOSE_PROJECT_NAME": PROJECT,
        "APP_ENV": "development",
        "PUBLIC_ORIGIN": LOCAL_HEALTH_ORIGIN,
        "SITE_ADDRESS": ":80",
        "ACME_EMAIL": "operador@example.invalid",
        "BIND_ADDRESS": "127.0.0.1",
        "HTTP_PORT": "18080",
        "HTTPS_PORT": "18443",
        "REQSYS_SECRET_DIR": root,
        "AZURE_TENANT_ID": ids[0],
        "AZURE_CLIENT_ID": ids[1],
    }
    return "".join(f"{k}={json.dumps(v)}\n" for k, v in values.items()).encode()


def proof_integrity(proof: dict) -> str:
    """Integridade canônica local; acesso autenticado pela DACL privada."""
    unsigned = {key: value for key, value in proof.items()
                if key != "proof_integrity_sha256"}
    data = json.dumps(
        unsigned, sort_keys=True, ensure_ascii=True,
        separators=(",", ":"), allow_nan=False
    ).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def source_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            digest.update(block)
    return digest.hexdigest()


def bounded_json(path: Path, private: WindowsPrivateFiles,
                 secure_new_file: bool = False) -> dict:
    no_reparse(path)
    if path.stat().st_size > 262144:
        raise PublishError("restore_evidence_too_large")
    if secure_new_file:
        private.secure(path)
    else:
        private.check(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PublishError("restore_evidence_not_object")
    return payload


def aggregate_restore_proof(raw: dict, expected_sha: str, backup_sha: str,
                            identity: dict, now: datetime) -> dict:
    required = {
        "schema_version": "1.0.0",
        "contract": "reqsys-sqlite-postgres-import",
        "status": "verified",
        "target_sha": expected_sha,
        "source_sha256": backup_sha,
        "digests_match": True,
        "independent_readback": True,
        "migration_committed": True,
        "sqlite_integrity_ok": True,
        "target_verified": True,
    }
    if any(raw.get(key) != value for key, value in required.items()):
        raise PublishError("restore_importer_proof_invalid")
    proof = {
        "schema_version": "1",
        "status": "verified",
        "host": HOST,
        "project": PROJECT,
        "target_sha": expected_sha,
        "source_sha256": backup_sha,
        "verified_at": raw.get("verified_at"),
        "source_rows": raw.get("source_rows"),
        "copied_rows": raw.get("copied_rows"),
        "table_counts": raw.get("table_counts"),
        "sqlite_integrity_ok": True,
        "target_verified": True,
        "digests_match": True,
        "independent_readback": True,
        "migration_committed": True,
        "database_identity": identity,
    }
    proof["proof_integrity_sha256"] = proof_integrity(proof)
    validate_restore_proof(proof, expected_sha, backup_sha, now)
    return proof


def validate_restore_proof(proof: dict, expected_sha: str,
                           backup_sha: str, now: datetime) -> dict[str, int]:
    if not isinstance(proof, dict):
        raise PublishError("restore_proof_not_object")
    if not DIGEST.fullmatch(backup_sha):
        raise PublishError("expected_backup_digest_required")
    exact = {
        "schema_version": "1",
        "status": "verified",
        "host": HOST,
        "project": PROJECT,
        "target_sha": expected_sha,
        "source_sha256": backup_sha,
        "sqlite_integrity_ok": True,
        "target_verified": True,
    }
    if any(proof.get(k) != v for k, v in exact.items()):
        raise PublishError("restore_proof_binding_invalid")
    try:
        verified = datetime.fromisoformat(
            str(proof["verified_at"]).replace("Z", "+00:00")
        )
        if verified.tzinfo is None:
            raise ValueError
        age = (now - verified).total_seconds()
    except (KeyError, TypeError, ValueError):
        raise PublishError("restore_proof_time_invalid")
    if not 0 <= age <= MAX_PROOF_AGE:
        raise PublishError("restore_proof_stale")
    rows = proof.get("source_rows")
    if (type(rows) is not int or rows <= 0
            or type(proof.get("copied_rows")) is not int
            or proof.get("copied_rows") != rows):
        raise PublishError("restore_proof_empty_or_incomplete")
    counts = proof.get("table_counts")
    if not isinstance(counts, dict) or not counts:
        raise PublishError("restore_proof_counts_invalid")
    if any(not isinstance(k, str) or not TABLE.fullmatch(k)
           or type(v) is not int or v < 0 for k, v in counts.items()):
        raise PublishError("restore_proof_counts_invalid")
    if sum(counts.values()) != rows:
        raise PublishError("restore_proof_counts_invalid")
    identity = proof.get("database_identity")
    if not isinstance(identity, dict) or identity.get("database") != "reqsys":
        raise PublishError("restore_proof_database_invalid")
    if not DIGEST.fullmatch(str(identity.get("container_id") or "")):
        raise PublishError("restore_proof_database_invalid")
    if not re.fullmatch(r"[0-9]{1,24}", str(
        identity.get("postgres_system_identifier") or ""
    )):
        raise PublishError("restore_proof_database_invalid")
    integrity = proof.get("proof_integrity_sha256")
    if not isinstance(integrity, str) or not DIGEST.fullmatch(integrity):
        raise PublishError("restore_proof_integrity_missing")
    if integrity != proof_integrity(proof):
        raise PublishError("restore_proof_integrity_mismatch")
    return counts


class Publisher:
    def __init__(self, source: Path, expected: str, private: WindowsPrivateFiles,
                 correlation: str):
        self.source = source.resolve()
        self.expected = validate_sha(expected)
        self.private = private
        self.correlation = correlation
        self.deadline = time.monotonic() + 840
        local = os.environ.get("LOCALAPPDATA", "")
        if not local or not Path(local).is_dir():
            raise PublishError("local_app_data_missing")
        self.root = Path(local) / "ReqSys" / "SelfHostedDev"
        self.env_file = self.root / "runtime.env"
        self.override = self.root / "compose.override.json"
        self.events: list[dict] = []

    def run(self, name: str, args: list[str], timeout: int = 60,
            input_text: str | None = None) -> str:
        remaining = int(self.deadline - time.monotonic())
        if remaining <= 0:
            raise PublishError("stage_deadline_exceeded")
        try:
            result = subprocess.run(
                args, cwd=self.source, input=input_text,
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", shell=False, check=False,
                timeout=min(timeout, remaining)
            )
        except subprocess.TimeoutExpired:
            self.events.append({"command": name, "outcome": "timeout"})
            raise PublishError(f"{name}_timeout")
        except OSError:
            self.events.append({"command": name, "outcome": "unavailable"})
            raise PublishError(f"{name}_unavailable")
        self.events.append({"command": name, "exit_code": result.returncode})
        if result.returncode:
            # Nunca incorporar stdout/stderr ou argumentos em erro/log.
            raise PublishError(f"{name}_failed")
        return result.stdout.strip()

    def compose(self, *args: str, timeout: int = 60,
                input_text: str | None = None) -> str:
        command = [
            "docker", "compose", "--project-name", PROJECT,
            "--project-directory", str(self.source / "infra/self-hosted"),
            "--env-file", str(self.env_file),
            "-f", str(self.source / "infra/self-hosted/compose.yml"),
            "-f", str(self.override), *args
        ]
        return self.run("compose_" + args[0], command, timeout, input_text)

    def validate_source(self) -> None:
        namespace = Path("C:/dev/chatgpt-workers").resolve()
        if not self.source.is_relative_to(namespace):
            raise PublishError("source_namespace_not_allowed")
        origin = self.run("source_origin", ["git", "remote", "get-url", "origin"])
        normalized = origin.strip().rstrip("/").removesuffix(".git").casefold()
        if normalized not in {
            f"https://github.com/{REPOSITORY}",
            f"git@github.com:{REPOSITORY}",
            f"ssh://git@github.com/{REPOSITORY}",
        }:
            raise PublishError("source_origin_mismatch")
        if self.run("source_head", ["git", "rev-parse", "HEAD"]) != self.expected:
            raise PublishError("source_head_mismatch")
        if self.run("source_state", [
            "git", "status", "--porcelain", "--untracked-files=all"
        ]):
            raise PublishError("source_tree_dirty")
        for name in ("compose.yml", "init-db.sh", "start_api.py", "Caddyfile"):
            path = self.source / "infra/self-hosted" / name
            no_reparse(path)
            if not path.is_file():
                raise PublishError("source_package_incomplete")
        if b"\r\n" in (self.source / "infra/self-hosted/init-db.sh").read_bytes():
            raise PublishError("linux_init_script_crlf")

    def validate_engine(self) -> None:
        if self.run("docker_engine", [
            "docker", "info", "--format", "{{.OSType}}"
        ]) != "linux":
            raise PublishError("docker_linux_engine_required")
        version = self.run("compose_version", [
            "docker", "compose", "version", "--short"
        ])
        match = re.match(r"v?([0-9]+)\.", version)
        if not match or int(match.group(1)) < 2:
            raise PublishError("compose_v2_or_newer_required")

    def key_handoff_module(self):
        path = self.source / "scripts/reqsys_dev_runtime_key_handoff.py"
        no_reparse(path)
        if not path.is_file():
            raise PublishError("key_handoff_package_required")
        spec = importlib.util.spec_from_file_location("reqsys_runtime_key_handoff", path)
        if spec is None or spec.loader is None:
            raise PublishError("key_handoff_package_required")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def preserve_runtime_keys(self) -> dict:
        self.root.parent.mkdir(parents=True, exist_ok=True)
        no_reparse(self.root.parent)
        module = self.key_handoff_module()
        try:
            metadata = module.preserve(self.root, self.expected, self.private)
        except module.HandoffError as exc:
            raise PublishError(exc.code) from exc
        self.events.append({
            "name": "original_runtime_keys_preserved", "ok": True,
            "source_written": False, "secret_values_exposed": False,
        })
        return metadata

    def require_key_handoff(self, source_container_id: str | None = None) -> dict:
        module = self.key_handoff_module()
        try:
            return module.validate_existing(
                self.root, self.expected, self.private, source_container_id
            )
        except module.HandoffError as exc:
            raise PublishError(exc.code) from exc

    def configure(self) -> tuple[str, str]:
        handoff = self.require_key_handoff()
        self.root.parent.mkdir(parents=True, exist_ok=True)
        no_reparse(self.root.parent)
        self.private.directory(self.root)
        initialize_secrets(self.root / "secrets", self.private, create_jwt=False)
        ids = discover_public_ids()
        self.private.preserving(
            self.env_file, render_config(self.root / "secrets", ids)
        )
        override = {
            "services": {
                name: {"labels": {"io.reqsys.selfhost.instance": INSTANCE}}
                for name in SERVICES
            }
        }
        override["services"]["api"]["environment"] = {
            "REQSYS_BUILD_SHA": self.expected,
            "REQSYS_REQUIRE_RUNTIME_KEY_HANDOFF": "1",
            "CORS_ORIGINS": f"{PAGES_UI_ORIGIN},{LOCAL_HEALTH_ORIGIN}",
            "APP_PUBLIC_URL": PAGES_UI_URL,
            # Preserve effective source claims together with the original HMAC key.
            "JWT_ISSUER": handoff["jwt_issuer"],
            "JWT_AUDIENCE": handoff["jwt_audience"],
            "REQSYS_VAULT_SERVICE_NAME": handoff["vault_service_name"],
            "REQSYS_DATA_DIR": "/data",
            "AI_CONVERSATION_ENCRYPTION_MODE": handoff["ai_mode"],
        }
        secret_dir = (self.root / "secrets").as_posix()
        override["secrets"] = {
            name: {"file": f"{secret_dir}/{name}"} for name in (
                "cofre_keyring_passphrase", "ai_conversation_content_encryption_key_b64"
            )
        }
        override["services"]["api"]["secrets"] = [
            "cofre_keyring_passphrase", "ai_conversation_content_encryption_key_b64"
        ]
        override["services"]["api"]["volumes"] = [{
            "type": "bind", "source": (self.root / "cofre-data").as_posix(),
            "target": "/data", "read_only": False,
        }]
        self.private.preserving(
            self.override,
            (json.dumps(override, indent=2, sort_keys=True) + "\n").encode()
        )
        self.compose("config", "--quiet")
        return ids

    def require_owned_project(self) -> None:
        ids = self.run("project_inventory", [
            "docker", "ps", "-a", "--filter",
            f"label=com.docker.compose.project={PROJECT}", "--format", "{{.ID}}"
        ]).splitlines()
        for container in ids:
            if not re.fullmatch(r"[0-9a-f]{12,64}", container):
                raise PublishError("project_inventory_invalid")
            labels = json.loads(self.run("project_identity", [
                "docker", "inspect", "--format", "{{json .Config.Labels}}", container
            ]))
            if not isinstance(labels, dict):
                raise PublishError("project_labels_invalid")
            if (labels.get("com.docker.compose.project") != PROJECT
                    or labels.get("io.reqsys.selfhost.instance") != INSTANCE):
                raise PublishError("existing_project_not_owned")

    def prepare(self) -> dict:
        self.validate_source()
        self.validate_engine()
        self.preserve_runtime_keys()
        ids = self.configure()
        self.require_owned_project()
        self.compose("build", "api", timeout=480)
        self.compose("up", "-d", "--wait", "--wait-timeout", "150",
                     "db", "redis", timeout=180)
        return {
            "status": "database_prepared",
            "restore_completed": False,
            "application_started": False,
            "azure_ids_available": bool(all(ids)),
            "usable": False,
        }

    def database_identity(self) -> dict:
        db = self.compose("ps", "--quiet", "db")
        if not re.fullmatch(r"[0-9a-f]{12,64}", db):
            raise PublishError("restore_target_db_not_unique")
        container = self.run("database_container_identity", [
            "docker", "inspect", "--format", "{{.Id}}", db
        ])
        if not DIGEST.fullmatch(container):
            raise PublishError("restore_target_container_invalid")
        system = self.compose(
            "exec", "-T", "db", "psql", "--no-psqlrc", "--quiet",
            "--tuples-only", "--no-align", "--set=ON_ERROR_STOP=1",
            "--username=reqsys_owner", "--dbname=reqsys", timeout=30,
            input_text="SELECT system_identifier FROM pg_control_system();\n"
        )
        if not re.fullmatch(r"[0-9]{1,24}", system):
            raise PublishError("restore_target_cluster_invalid")
        return {
            "container_id": container,
            "postgres_system_identifier": system,
            "database": "reqsys",
        }

    def cleanup_importer(self, name: str, attempt: str) -> None:
        """Encerra apenas o container efêmero desta tentativa, sem remover volumes."""
        if not re.fullmatch(r"[0-9a-f]{24}", attempt) or name != "reqsys-dev-restore-" + attempt:
            raise PublishError("restore_cleanup_identity_invalid")
        try:
            inspected = subprocess.run(
                ["docker", "inspect", "--format", "{{json .Config.Labels}}", name],
                cwd=self.source, capture_output=True, text=True,
                encoding="utf-8", errors="replace", shell=False, timeout=10
            )
        except (OSError, subprocess.TimeoutExpired):
            raise PublishError("restore_cleanup_inspect_unavailable") from None
        if inspected.returncode:
            missing = ("no such object:" in inspected.stderr.casefold()
                       or "no such container:" in inspected.stderr.casefold())
            if missing and name in inspected.stderr:
                self.events.append({"command": "restore_cleanup", "outcome": "already_removed"})
                return
            raise PublishError("restore_cleanup_inspect_failed")
        try:
            labels = json.loads(inspected.stdout)
        except (TypeError, ValueError):
            raise PublishError("restore_cleanup_labels_invalid") from None
        exact = {
            "com.docker.compose.project": PROJECT,
            "com.docker.compose.service": "api",
            "io.reqsys.selfhost.instance": INSTANCE,
            "io.reqsys.selfhost.restore_attempt": attempt,
        }
        if not isinstance(labels, dict) or any(labels.get(k) != v for k, v in exact.items()):
            raise PublishError("restore_cleanup_owner_mismatch")
        try:
            removed = subprocess.run(
                ["docker", "rm", "--force", name], cwd=self.source,
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                shell=False, timeout=10
            )
        except (OSError, subprocess.TimeoutExpired):
            raise PublishError("restore_cleanup_remove_unavailable") from None
        self.events.append({"command": "restore_cleanup", "exit_code": removed.returncode})
        if removed.returncode:
            raise PublishError("restore_cleanup_remove_failed")


    def restore(self, backup_sha: str) -> dict:
        self.validate_source()
        self.validate_engine()
        if not DIGEST.fullmatch(backup_sha):
            raise PublishError("expected_backup_digest_required")
        migration = self.root / "Migration"
        source = migration / "restored-dev.sqlite"
        self.private.check(self.root)
        self.private.check(migration)
        self.private.check(source)
        if any(Path(str(source) + suffix).exists()
               for suffix in ("-wal", "-shm", "-journal")):
            raise PublishError("restore_source_not_standalone")
        if source_digest(source) != backup_sha:
            raise PublishError("restore_source_sha256_mismatch")
        importer = self.source / "scripts/import_self_hosted_dev_sqlite.py"
        no_reparse(importer)
        if not importer.is_file():
            raise PublishError("restore_importer_missing")
        self.configure()
        self.require_owned_project()
        proof_file = self.root / "restore-proof.json"
        now = datetime.now(timezone.utc)
        if proof_file.exists():
            proof = bounded_json(proof_file, self.private)
            counts = validate_restore_proof(proof, self.expected, backup_sha, now)
            self.verify_live_restore(proof, counts)
            return {
                "status": "database_restored",
                "restore_completed": True,
                "restored_rows": proof["copied_rows"],
                "import_replayed": False,
                "existing_verified_restore_reused": True,
                "application_started": False,
                "usable": False,
            }
        # Somente banco/fila; a API não inicia nem dispara seed de startup.
        self.compose("up", "-d", "--wait", "--wait-timeout", "150",
                     "db", "redis", timeout=180)
        identity = self.database_identity()
        evidence_root = migration / "ImportEvidence"
        self.private.directory(evidence_root)
        attempt = secrets.token_hex(12)
        container_name = "reqsys-dev-restore-" + attempt
        attempt_root = evidence_root / ("attempt-" + attempt)
        self.private.directory(attempt_root)
        raw_file = attempt_root / "sqlite-postgres-import.json"
        command = [
            "run", "--rm", "--no-deps", "--entrypoint", "python",
            "--name", container_name,
            "--label", "io.reqsys.selfhost.restore_attempt=" + attempt,
            "--volume", f"{importer.as_posix()}:/opt/reqsys/import_self_hosted_dev_sqlite.py:ro",
            "--volume", f"{source.as_posix()}:/migration/source.db:ro",
            "--volume", f"{attempt_root.as_posix()}:/migration-evidence",
            "api", "/opt/reqsys/import_self_hosted_dev_sqlite.py",
            "--expected-sha256", backup_sha,
        ]
        try:
            self.compose(*command, timeout=540)
        except PublishError:
            if raw_file.is_file():
                raw = bounded_json(raw_file, self.private, secure_new_file=True)
                self.events.append({
                    "command": "restore_importer",
                    "migration_committed": raw.get("migration_committed") is True,
                })
                error = raw.get("error_code")
                if isinstance(error, str) and re.fullmatch(r"[a-z_]{1,80}", error):
                    raise PublishError("restore_importer_" + error) from None
            raise
        finally:
            self.cleanup_importer(container_name, attempt)
        raw = bounded_json(raw_file, self.private, secure_new_file=True)
        proof = aggregate_restore_proof(
            raw, self.expected, backup_sha, identity, datetime.now(timezone.utc)
        )
        if source_digest(source) != backup_sha:
            raise PublishError("restore_source_changed_after_import")
        if self.database_identity() != identity:
            raise PublishError("restore_target_changed_during_import")
        counts = validate_restore_proof(
            proof, self.expected, backup_sha, datetime.now(timezone.utc)
        )
        self.verify_live_restore(proof, counts)
        # O_EXCL + preservação: nunca substituir outra prova/instância.
        self.private.preserving(
            proof_file, (json.dumps(proof, sort_keys=True, indent=2) + "\n").encode()
        )
        return {
            "status": "database_restored",
            "restore_completed": True,
            "restored_rows": proof["copied_rows"],
            "import_replayed": False,
            "existing_verified_restore_reused": False,
            "application_started": False,
            "usable": False,
        }


    def verify_live_restore(self, proof: dict, counts: dict[str, int]) -> None:
        db = self.compose("ps", "--quiet", "db")
        if not re.fullmatch(r"[0-9a-f]{12,64}", db):
            raise PublishError("restore_target_db_not_unique")
        container = self.run("database_container_identity", [
            "docker", "inspect", "--format", "{{.Id}}", db
        ])
        identity = proof["database_identity"]
        if container != identity["container_id"]:
            raise PublishError("restore_target_container_changed")
        sql = [
            "BEGIN READ ONLY;",
            "SELECT 'identity|' || system_identifier FROM pg_control_system();",
        ]
        for name in sorted(counts):
            sql.append(f'SELECT \'{name}|\' || COUNT(*) FROM "{name}";')
        sql.append("COMMIT;")
        output = self.compose(
            "exec", "-T", "db", "psql", "--no-psqlrc", "--quiet",
            "--tuples-only", "--no-align", "--set=ON_ERROR_STOP=1",
            "--username=reqsys_owner", "--dbname=reqsys",
            timeout=90, input_text="\n".join(sql) + "\n"
        )
        observed = {}
        for line in output.splitlines():
            if "|" not in line:
                continue
            name, value = line.split("|", 1)
            observed[name] = value.strip()
        if observed.pop("identity", None) != identity["postgres_system_identifier"]:
            raise PublishError("restore_target_cluster_changed")
        if observed != {name: str(count) for name, count in counts.items()}:
            raise PublishError("restore_live_counts_mismatch")

    def postgres_restorer_module(self):
        path = self.source / "scripts/restore_self_hosted_dev_postgres.py"
        no_reparse(path)
        spec = importlib.util.spec_from_file_location("reqsys_postgres_restorer", path)
        if spec is None or spec.loader is None:
            raise PublishError("postgres_restore_module_missing")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def restore_postgres(self) -> dict:
        module = self.postgres_restorer_module()
        try:
            proof = module.Restorer(self).restore()
        except module.RestoreError as error:
            self.events.append({
                "command": "postgres_restore",
                "migration_committed": error.committed,
            })
            raise PublishError("postgres_" + error.code) from None
        return {
            "status": "database_restored",
            "restore_completed": True,
            "restored_rows": proof["copied_rows"],
            "archive_content_compared": True,
            "sequences_verified": True,
            "runtime_keys_preserved": True,
            "application_started": False,
            "current_source_freshness_verified": False,
            "usable": False,
        }

    def activate(self, backup_sha: str) -> dict:
        self.validate_source()
        self.validate_engine()
        ids = self.configure()
        self.require_owned_project()
        if not all(ids):
            raise PublishError("azure_public_ids_missing")
        # The Noteri SQLite rehearsal cannot authorize the current DEV cutover.
        # PostgreSQL proof independently checks archive COPY digests, schema,
        # sequence state, cluster identity and the preserved runtime keys.
        pg = self.postgres_restorer_module()
        try:
            proof = pg.verify_existing(self, backup_sha)
        except pg.RestoreError as error:
            raise PublishError("postgres_" + error.code) from None
        self.compose("build", "frontend", timeout=360)
        self.compose("up", "-d", "--wait", "--wait-timeout", "180", timeout=210)
        endpoints = {}
        for path in ("/api/health", "/api/runtime/health",
                     "/api/runtime/readiness", "/api/runtime/build-info",
                     "/api/v1/auth/config"):
            endpoints[path] = get_json("http://127.0.0.1:18080" + path)
        for path in ("/api/health", "/api/runtime/health",
                     "/api/runtime/readiness", "/api/runtime/build-info"):
            validate_health_payload(path, endpoints[path])
        build = endpoints["/api/runtime/build-info"]
        if build.get("build_sha") != self.expected:
            raise PublishError("published_build_sha_mismatch")
        auth = endpoints["/api/v1/auth/config"]
        if (auth.get("azure_enabled") is not True
                or auth.get("demo_login_enabled") is not False
                or (auth.get("azure_tenant_id"), auth.get("azure_client_id")) != ids):
            raise PublishError("published_auth_configuration_invalid")
        request = urllib.request.Request("http://127.0.0.1:18080/")
        with urllib.request.build_opener(RejectRedirect()).open(
            request, timeout=8
        ) as response:
            html = response.read(16384).lower()
            if response.status != 200 or b"<html" not in html:
                raise PublishError("frontend_smoke_failed")
        return {
            "status": "isolated_application_published",
            "restore_completed": True,
            "restore_verified_before_boot": True,
            "restored_rows": proof["copied_rows"],
            "application_started": True,
            "smoke_passed": True,
            "authenticated_flow_verified": False,
            "public_ingress_verified": False,
            "local_url": "http://localhost:18080/",
            "usable": False,
        }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "restore", "restore-postgres", "activate"))
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--backup-sha256", default="")
    args = parser.parse_args(argv)
    evidence = {
        "schema_version": "1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "host": HOST,
        "project": PROJECT,
        "phase": args.phase,
        "target_sha": args.expected_sha,
        "correlation_id": args.correlation_id,
        "dev_pointer_changed": False,
        "production_touched": False,
        "fly_used": False,
        "secret_values_exposed": False,
        "usable": False,
    }
    publisher = None
    code = 2
    try:
        require_host()
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,120}", args.correlation_id):
            raise PublishError("invalid_correlation_id")
        publisher = Publisher(
            args.source_root, args.expected_sha,
            WindowsPrivateFiles(), args.correlation_id
        )
        if args.phase == "prepare":
            result = publisher.prepare()
        elif args.phase == "restore":
            result = publisher.restore(args.backup_sha256)
        elif args.phase == "restore-postgres":
            result = publisher.restore_postgres()
        else:
            result = publisher.activate(args.backup_sha256)
        evidence.update(result)
        evidence["operation_succeeded"] = True
        code = 0
    except Exception as exc:
        evidence.update({
            "status": "blocked",
            "operation_succeeded": False,
            "error": exc.code if isinstance(exc, PublishError)
                     else f"operation_{type(exc).__name__}",
        })
    if publisher is not None:
        evidence["commands"] = publisher.events
        try:
            if publisher.root.is_dir():
                publisher.private.evidence(
                    publisher.root / f"{args.phase}-evidence.json",
                    (json.dumps(evidence, indent=2, sort_keys=True) + "\n").encode()
                )
        except Exception:
            evidence["evidence_persisted"] = False
            evidence["operation_succeeded"] = False
            evidence["status"] = "blocked"
            code = 2
    print(json.dumps(evidence, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
