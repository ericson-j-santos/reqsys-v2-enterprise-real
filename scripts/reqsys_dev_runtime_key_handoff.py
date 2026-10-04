"""Preserve selected keys from the fixed local DEV runtime; never print values."""
from __future__ import annotations

import base64
import json
import importlib.util
from pathlib import Path
import queue
import re
import subprocess
import threading
import time

SOURCE_PROJECT = "wt-pc24x7-piloto"
SOURCE_CONTAINER = "wt-pc24x7-piloto-api-1"
TARGET_HOST = "DESKTOP-PDQK954"
SCHEMA = "reqsys-local-dev-runtime-key-handoff-v1"
ENTROPY = SCHEMA.encode("ascii")
MAX_KEYRING = 1_048_576
MAX_CAPTURE = 2_097_152
MAX_SECRET = 65_536
SECRET_FIELDS = {
    "jwt_secret": "jwt_secret",
    "cofre_keyring_passphrase": "cofre_keyring_passphrase",
    "ai_conversation_content_encryption_key_b64": "ai_conversation_content_encryption_key_b64",
}
PAYLOAD_FIELDS = {
    "schema", "target_sha", "target_host", "source_project", "source_container_id", "created_at",
    "jwt_secret", "cofre_keyring_passphrase", "vault_service_name",
    "ai_conversation_content_encryption_key_b64", "ai_encrypted_count", "ai_mode",
    "keyring_cipher_b64", "jwt_resolution", "ai_resolution",
    "source_database", "source_role", "source_postgres_version", "jwt_issuer", "jwt_audience",
}

# Executed only inside the exact existing container. No writes, token acquisition,
# remote vault calls, arbitrary files, URLs, or values in process arguments.
SOURCE_COLLECTOR = r'''
import base64, hashlib, io, json, os, re
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from dotenv import dotenv_values

def need(ok):
    if not ok:
        raise RuntimeError("source_key_context_unavailable")

with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
    passphrase = os.environ.get("COFRE_KEYRING_PASSPHRASE", "")
    if not passphrase:
        fixed = Path("/run/secrets/cofre_keyring_passphrase")
        need(fixed.is_file() and fixed.stat().st_size <= 65536)
        # Match the existing shell command substitution; preserve any final CR.
        passphrase = fixed.read_bytes().decode("utf-8").rstrip("\n")
    need(bool(passphrase) and "\x00" not in passphrase)
    os.environ["COFRE_KEYRING_PASSPHRASE"] = passphrase
    need(os.environ.get("REQSYS_DATA_DIR", "/data") == "/data")
    path = Path("/data/cofre-keyring.enc")
    need(path.is_file() and 28 <= path.stat().st_size <= 1048576)
    raw = path.read_bytes()
    from app.core import secrets as secrets_core
    # This probe is explicitly local. Do not contact an optional remote resolver.
    secrets_core.read_secret_from_remote_vault = lambda _key: None
    from app.core.keyring_backend import FileEncryptedKeyring
    backend = FileEncryptedKeyring(path="/data", passphrase=passphrase)
    import keyring
    keyring.set_keyring(backend)
    service = secrets_core._vault_service_name()
    need(bool(service) and len(service.encode("utf-8")) <= 256)
    entries = backend._load()
    slot = entries.get(service, {}).get("__master_key__")
    need(isinstance(slot, str) and len(base64.b64decode(slot, validate=True)) == 32)
    local_jwt = secrets_core.read_secret_from_vault("JWT_SECRET")
    from app.core import config as config_core
    settings = config_core.settings
    effective_jwt = settings.jwt_secret
    candidates = [
        ("env", os.environ.get("JWT_SECRET", "")),
        ("vault", local_jwt or ""),
    ]
    env_path = config_core._env_file
    if env_path.is_file():
        need(env_path.stat().st_size <= 1048576)
        candidates.append(("env_file", dotenv_values(env_path).get("JWT_SECRET") or ""))
    matches = [name for name, value in candidates if value and value == effective_jwt]
    need(bool(matches) and isinstance(effective_jwt, str))
    local_ai = secrets_core.read_secret_from_vault("AI_CONVERSATION_CONTENT_ENCRYPTION_KEY_B64")
    ai = local_ai or os.environ.get("AI_CONVERSATION_CONTENT_ENCRYPTION_KEY_B64", "")
    ai_resolution = "vault" if local_ai else ("env" if ai else "absent")
    mode = os.environ.get("AI_CONVERSATION_ENCRYPTION_MODE", "off").strip().lower()
    need(mode in {"off", "disabled", "legacy", "enforce"})
    if ai:
        need(len(base64.b64decode(ai, validate=True)) == 32)
    db_url = make_url(settings.database_url)
    need(db_url.get_backend_name() == "postgresql" and db_url.host == "db"
         and (db_url.port or 5432) == 5432 and db_url.database == "reqsys"
         and db_url.username == "reqsys_app")
    engine = create_engine(db_url, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            identity = connection.execute(text(
                "SELECT current_database(), current_user, current_setting('server_version_num')"
            )).one()
            need(identity[0] == "reqsys" and identity[1] == "reqsys_app"
                 and str(identity[2]).startswith("16"))
            present = connection.execute(text(
                "SELECT to_regclass('public.ai_conversation_messages')"
            )).scalar()
            encrypted_count = 0
            if present:
                encrypted_count = int(connection.execute(text(
                    "SELECT count(*) FROM public.ai_conversation_messages "
                    "WHERE content LIKE 'enc:v1:%'"
                )).scalar())
            connection.rollback()
    finally:
        engine.dispose()
    need(bool(ai) or (encrypted_count == 0 and mode != "enforce"))
    need(path.read_bytes() == raw)
    result = {
        "jwt_secret": effective_jwt,
        "cofre_keyring_passphrase": passphrase,
        "vault_service_name": service,
        "ai_conversation_content_encryption_key_b64": ai,
        "ai_encrypted_count": encrypted_count, "ai_mode": mode,
        "keyring_cipher_b64": base64.b64encode(raw).decode("ascii"),
        "jwt_resolution": matches[0], "ai_resolution": ai_resolution,
        "source_database": identity[0], "source_role": identity[1],
        "source_postgres_version": str(identity[2]),
        "jwt_issuer": settings.jwt_issuer, "jwt_audience": settings.jwt_audience,
    }
    need(all(isinstance(result[name], str)
             and len(result[name].encode("utf-8")) <= 65536
             and "\x00" not in result[name]
             for name in ("jwt_secret", "cofre_keyring_passphrase",
                          "ai_conversation_content_encryption_key_b64")))
print(json.dumps(result, separators=(",", ":"), sort_keys=True))
'''


class HandoffError(RuntimeError):
    def __init__(self, code: str):
        self.code = code if re.fullmatch(r"[a-z0-9_]+", code) else "key_handoff_failed"
        super().__init__(self.code)


def require(ok: bool, code: str) -> None:
    if not ok:
        raise HandoffError(code)


def parse_json(raw: bytes) -> dict:
    require(0 < len(raw) <= MAX_CAPTURE, "key_snapshot_size_invalid")
    def pairs(items):
        output = {}
        for key, value in items:
            require(key not in output, "key_snapshot_json_invalid")
            output[key] = value
        return output
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
    except (ValueError, UnicodeError) as exc:
        raise HandoffError("key_snapshot_json_invalid") from exc
    require(isinstance(value, dict), "key_snapshot_json_invalid")
    return value


def capture(argv: list[str], timeout: int = 90) -> bytes:
    """Bounded subprocess bytes; stderr and stdin cannot expose selected keys."""
    events = queue.Queue(maxsize=2)
    try:
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, shell=False)
    except OSError as exc:
        raise HandoffError("key_source_command_unavailable") from exc
    def reader():
        try:
            while True:
                chunk = process.stdout.read(65536)
                events.put(chunk)
                if not chunk:
                    return
        except Exception:
            events.put(None)
    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    deadline = time.monotonic() + timeout
    result = bytearray()
    try:
        while True:
            left = deadline - time.monotonic()
            require(left > 0, "key_source_command_timeout")
            try:
                chunk = events.get(timeout=left)
            except queue.Empty as exc:
                raise HandoffError("key_source_command_timeout") from exc
            require(chunk is not None, "key_source_command_failed")
            if not chunk:
                break
            require(len(result) + len(chunk) <= MAX_CAPTURE, "key_source_output_limit")
            result.extend(chunk)
        require(process.wait(timeout=max(0.1, deadline - time.monotonic())) == 0,
                "key_source_command_failed")
        return bytes(result)
    except subprocess.TimeoutExpired as exc:
        raise HandoffError("key_source_command_timeout") from exc
    finally:
        if process.poll() is None:
            process.kill()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                # Limpeza best-effort: o processo já recebeu kill e pode encerrar depois do timeout.
                pass
        process.stdout.close()
        thread.join(timeout=0.1)


def inspect_source() -> str:
    format_text = (
        '{"id":{{json .Id}},"labels":{{json .Config.Labels}},'
        '"mounts":{{json .Mounts}},"running":{{json .State.Running}}}'
    )
    metadata = parse_json(capture([
        "docker", "inspect", "--format", format_text, SOURCE_CONTAINER,
    ], timeout=30))
    container_id = metadata.get("id")
    labels = metadata.get("labels") or {}
    require(isinstance(container_id, str) and re.fullmatch(r"[a-f0-9]{64}", container_id)
            and metadata.get("running") is True
            and labels.get("com.docker.compose.project") == SOURCE_PROJECT
            and labels.get("com.docker.compose.service") == "api",
            "key_source_container_unverified")
    mounts = metadata.get("mounts")
    require(isinstance(mounts, list)
            and any(isinstance(item, dict) and item.get("Destination") == "/data"
                    and item.get("Type") == "volume" for item in mounts),
            "key_source_data_mount_unverified")
    return container_id


def validate_payload(payload: dict, target_sha: str) -> bytes:
    require(set(payload) == PAYLOAD_FIELDS
            and payload.get("schema") == SCHEMA
            and payload.get("target_sha") == target_sha
            and payload.get("target_host") == TARGET_HOST
            and re.fullmatch(r"[a-f0-9]{40}", target_sha) is not None
            and payload.get("source_project") == SOURCE_PROJECT
            and isinstance(payload.get("source_container_id"), str)
            and re.fullmatch(r"[a-f0-9]{64}", payload["source_container_id"]) is not None,
            "key_snapshot_binding_invalid")
    require(type(payload.get("created_at")) is int and payload["created_at"] > 0,
            "key_snapshot_time_invalid")
    for field in SECRET_FIELDS:
        value = payload.get(field)
        require(isinstance(value, str) and len(value.encode("utf-8")) <= MAX_SECRET
                and "\x00" not in value, "key_material_encoding_invalid")
    require(bool(payload["jwt_secret"]) and bool(payload["cofre_keyring_passphrase"]),
            "original_key_material_required")
    for field in ("jwt_issuer", "jwt_audience"):
        require(isinstance(payload.get(field), str)
                and len(payload[field].encode("utf-8")) <= 4096
                and "\x00" not in payload[field], "original_jwt_claim_config_invalid")
    service = payload.get("vault_service_name")
    require(isinstance(service, str) and re.fullmatch(r"[A-Za-z0-9_.:/ -]{1,256}", service)
            is not None, "vault_service_name_invalid")
    require(payload.get("jwt_resolution") in {"env", "vault", "env_file"}
            and payload.get("ai_resolution") in {"env", "vault", "absent"}
            and payload.get("source_database") == "reqsys"
            and payload.get("source_role") == "reqsys_app"
            and isinstance(payload.get("source_postgres_version"), str)
            and re.fullmatch(r"16[0-9]{4}", payload["source_postgres_version"]) is not None,
            "original_key_resolution_unverified")
    count = payload.get("ai_encrypted_count")
    require(type(count) is int and count >= 0
            and payload.get("ai_mode") in {"off", "disabled", "legacy", "enforce"},
            "ai_key_context_invalid")
    ai = payload["ai_conversation_content_encryption_key_b64"]
    require(bool(ai) or (count == 0 and payload["ai_mode"] != "enforce"
                        and payload["ai_resolution"] == "absent"),
            "original_ai_encryption_key_required")
    try:
        if ai:
            require(len(base64.b64decode(ai, validate=True)) == 32,
                    "original_ai_encryption_key_invalid")
        encoded = payload.get("keyring_cipher_b64")
        require(isinstance(encoded, str) and len(encoded) <= 4 * ((MAX_KEYRING + 2) // 3),
                "keyring_ciphertext_size_invalid")
        ciphertext = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise HandoffError("key_material_encoding_invalid") from exc
    require(28 <= len(ciphertext) <= MAX_KEYRING, "keyring_ciphertext_size_invalid")
    return ciphertext


_TRANSPORT = None


def windows_crypto():
    global _TRANSPORT
    if _TRANSPORT is None:
        path = Path(__file__).with_name("dev_backup_transport.py")
        spec = importlib.util.spec_from_file_location("key_handoff_transport_libraries", path)
        require(spec is not None and spec.loader is not None, "key_handoff_libraries_unavailable")
        _TRANSPORT = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_TRANSPORT)
    _TRANSPORT.initialize_windows_libraries()
    import win32crypt
    return win32crypt


def protect(raw: bytes) -> bytes:
    return windows_crypto().CryptProtectData(raw, SCHEMA, ENTROPY, None, None, 1)


def unprotect(raw: bytes) -> bytes:
    return windows_crypto().CryptUnprotectData(raw, ENTROPY, None, None, 1)[1]


def snapshot_path(root: Path) -> Path:
    return root / "Migration/runtime-keys.dpapi"


def load_snapshot(root: Path, target_sha: str, private) -> dict:
    path = snapshot_path(root)
    private.check(path)
    require(path.is_file() and 0 < path.stat().st_size <= MAX_CAPTURE + 65536,
            "key_snapshot_size_invalid")
    try:
        payload = parse_json(unprotect(path.read_bytes()))
    except HandoffError:
        raise
    except Exception as exc:
        raise HandoffError("key_snapshot_dpapi_unavailable") from exc
    validate_payload(payload, target_sha)
    return payload


def public_metadata(payload: dict) -> dict:
    return {
        "status": "verified", "source_project": SOURCE_PROJECT,
        "source_container_id": payload["source_container_id"], "target_sha": payload["target_sha"],
        "vault_service_name": payload["vault_service_name"], "created_at": payload["created_at"],
        "jwt_issuer": payload["jwt_issuer"], "jwt_audience": payload["jwt_audience"],
        "jwt_preserved": True, "cofre_preserved": True,
        "ai_key_preserved": bool(payload["ai_conversation_content_encryption_key_b64"]),
        "ai_encrypted_count": payload["ai_encrypted_count"], "ai_mode": payload["ai_mode"],
        "secret_values_exposed": False, "source_written": False,
    }


def validate_existing(root: Path, target_sha: str, private,
                      source_container_id: str | None = None) -> dict:
    payload = load_snapshot(root, target_sha, private)
    if source_container_id is not None:
        require(payload["source_container_id"] == source_container_id,
                "key_snapshot_source_container_mismatch")
    for field, filename in SECRET_FIELDS.items():
        path = root / "secrets" / filename
        private.check(path)
        expected = payload[field].encode("utf-8")
        require(path.is_file() and path.stat().st_size == len(expected)
                and path.read_bytes() == expected, "original_key_fidelity_failed")
    file_path = root / "cofre-data/cofre-keyring.enc"
    private.check(file_path)
    ciphertext = validate_payload(payload, target_sha)
    require(file_path.is_file() and file_path.stat().st_size == len(ciphertext)
            and file_path.read_bytes() == ciphertext, "original_keyring_fidelity_failed")
    return public_metadata(payload)


def preserve(root: Path, target_sha: str, private) -> dict:
    """Snapshot source read-only, seal with user DPAPI, then preserve exact bytes."""
    private.directory(root)
    private.directory(root / "Migration")
    before = inspect_source()
    captured = parse_json(capture([
        "docker", "exec", "--workdir", "/app", SOURCE_CONTAINER,
        "python", "-c", SOURCE_COLLECTOR,
    ]))
    require(inspect_source() == before, "key_source_container_changed")
    captured.update({
        "schema": SCHEMA, "target_sha": target_sha, "target_host": TARGET_HOST,
        "source_project": SOURCE_PROJECT,
        "source_container_id": before, "created_at": int(time.time()),
    })
    ciphertext = validate_payload(captured, target_sha)
    path = snapshot_path(root)
    if path.exists():
        old = load_snapshot(root, target_sha, private)
        # A replay may differ only in the capture timestamp; never change the snapshot.
        compare = dict(captured)
        compare["created_at"] = old["created_at"]
        require(old == compare, "existing_key_snapshot_conflict")
        captured = old
    else:
        raw = json.dumps(captured, sort_keys=True, separators=(",", ":")).encode("utf-8")
        try:
            sealed = protect(raw)
        except Exception as exc:
            raise HandoffError("key_snapshot_dpapi_unavailable") from exc
        require(0 < len(sealed) <= MAX_CAPTURE + 65536, "key_snapshot_size_invalid")
        private.create(path, sealed)
    private.directory(root / "secrets")
    private.directory(root / "cofre-data")
    for field, filename in SECRET_FIELDS.items():
        private.preserving(root / "secrets" / filename, captured[field].encode("utf-8"))
    private.preserving(root / "cofre-data/cofre-keyring.enc", ciphertext)
    return validate_existing(root, target_sha, private, before)
