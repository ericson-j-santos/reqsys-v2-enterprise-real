"""Fixed DEV backup handoff: Noteri -> PC24x7. No network or shell executor."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import socket
import sqlite3
import stat
import time
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

SCHEMA = "reqsys-dev-noteri-pc24x7-backup-v1"
SOURCE_HOST = "Noteri"
TARGET_HOST = "DESKTOP-PDQK954"
SNAPSHOT_ID = "c017334cd021ec734bfecae44622c0196b44b4a386d646aebd2ec5c47d6e53f0"
SQLITE_SHA256 = "f300a4e003bcb1195aab7dbf2a3fbe31c164cddbf1abd55f5619cd9c4043cd7a"
SQLITE_BYTES = 237568
EXPECTED_TABLES = 11
EXPECTED_ROWS = 210
TTL = 3600
MAX_ENVELOPE_BYTES = 2_000_000
DPAPI_ENTROPY = SCHEMA.encode("ascii")
HEADER_FIELDS = {
    "schema", "source_host", "target_host", "snapshot_id", "sqlite_sha256",
    "sqlite_bytes", "created_at", "expires_at", "source_run_id", "source_sha",
    "recipient_sha256",
}


class TransportError(RuntimeError):
    """Only sanitized, constant failure codes may leave the process."""


def reject(code: str) -> None:
    raise TransportError(code)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def unb64(value: object, maximum: int) -> bytes:
    if not isinstance(value, str) or len(value) > 4 * ((maximum + 2) // 3):
        reject("invalid_encoded_field")
    try:
        result = base64.b64decode(value, validate=True)
    except (ValueError, TypeError):
        reject("invalid_encoded_field")
    if len(result) > maximum:
        reject("encoded_field_too_large")
    return result


def exact_host(expected: str) -> None:
    if os.name != "nt" or socket.gethostname().casefold() != expected.casefold():
        reject("fixed_windows_host_required")


def provenance(run_id: object, source_sha: object) -> tuple[int, str]:
    if isinstance(run_id, bool) or not str(run_id).isdigit():
        reject("invalid_source_run_id")
    run_id = int(run_id)
    if not 0 < run_id < 2**63:
        reject("invalid_source_run_id")
    if not isinstance(source_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        reject("invalid_source_sha")
    return run_id, source_sha


def public_der(key: rsa.RSAPublicKey) -> bytes:
    if not isinstance(key, rsa.RSAPublicKey) or key.key_size != 3072:
        reject("recipient_rsa_3072_required")
    return key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)


def oaep() -> padding.OAEP:
    return padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=DPAPI_ENTROPY)


def verify_sqlite(data: bytes) -> dict:
    if len(data) != SQLITE_BYTES or not hmac.compare_digest(digest(data), SQLITE_SHA256):
        reject("fixed_backup_digest_mismatch")
    if not data.startswith(b"SQLite format 3\0"):
        reject("sqlite_header_mismatch")
    db = sqlite3.connect(":memory:")
    try:
        db.deserialize(data)
        if db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            reject("sqlite_integrity_failed")
        tables = [row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )]
        rows = sum(db.execute('SELECT COUNT(*) FROM "' + name.replace('"', '""') + '"').fetchone()[0]
                   for name in tables)
        if len(tables) != EXPECTED_TABLES or rows != EXPECTED_ROWS:
            reject("fixed_backup_counts_mismatch")
        return {"sqlite_sha256": SQLITE_SHA256, "sqlite_bytes": len(data),
                "tables": len(tables), "rows": rows, "integrity": "ok"}
    except sqlite3.Error:
        reject("sqlite_validation_failed")
    finally:
        db.close()


def seal_sqlite(data: bytes, recipient: rsa.RSAPublicKey,
                run_id: int, source_sha: str, *, now: int | None = None) -> bytes:
    """Pure crypto core. Fixed operational wrapper supplies the verified Restic dump."""
    verify_sqlite(data)
    run_id, source_sha = provenance(run_id, source_sha)
    now = int(time.time()) if now is None else int(now)
    header = {
        "schema": SCHEMA, "source_host": SOURCE_HOST, "target_host": TARGET_HOST,
        "snapshot_id": SNAPSHOT_ID, "sqlite_sha256": SQLITE_SHA256,
        "sqlite_bytes": SQLITE_BYTES, "source_run_id": run_id, "source_sha": source_sha,
        "recipient_sha256": digest(public_der(recipient)),
        "created_at": now, "expires_at": now + TTL,
    }
    aes_key, nonce = os.urandom(32), os.urandom(12)
    ciphertext = AESGCM(aes_key).encrypt(nonce, data, canonical(header))
    return canonical({"header": header, "nonce_b64": b64(nonce),
                      "sealed_key_b64": b64(recipient.encrypt(aes_key, oaep())),
                      "ciphertext_b64": b64(ciphertext)})


def open_sqlite(envelope_bytes: bytes, private_key: rsa.RSAPrivateKey, *,
                expected_run_id: int, expected_source_sha: str,
                expected_envelope_sha256: str, now: int | None = None) -> tuple[bytes, dict]:
    """Exact artifact run/SHA/digest must come from the separately reviewed workflow."""
    if len(envelope_bytes) > MAX_ENVELOPE_BYTES:
        reject("envelope_too_large")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_envelope_sha256 or ""):
        reject("invalid_expected_envelope_digest")
    if not hmac.compare_digest(digest(envelope_bytes), expected_envelope_sha256):
        reject("artifact_digest_mismatch")
    expected_run_id, expected_source_sha = provenance(expected_run_id, expected_source_sha)
    try:
        envelope = json.loads(envelope_bytes)
    except (ValueError, UnicodeError):
        reject("invalid_envelope_json")
    if not isinstance(envelope, dict) or set(envelope) != {
            "header", "nonce_b64", "sealed_key_b64", "ciphertext_b64"}:
        reject("invalid_envelope_schema")
    header = envelope["header"]
    if not isinstance(header, dict) or set(header) != HEADER_FIELDS:
        reject("invalid_binding_schema")
    for field, expected in {
        "schema": SCHEMA, "source_host": SOURCE_HOST, "target_host": TARGET_HOST,
        "snapshot_id": SNAPSHOT_ID, "sqlite_sha256": SQLITE_SHA256,
        "sqlite_bytes": SQLITE_BYTES, "source_run_id": expected_run_id,
        "source_sha": expected_source_sha,
        "recipient_sha256": digest(public_der(private_key.public_key())),
    }.items():
        if type(header[field]) is not type(expected) or header[field] != expected:
            reject("envelope_binding_mismatch")
    now = int(time.time()) if now is None else int(now)
    created, expires = header["created_at"], header["expires_at"]
    if type(created) is not int or type(expires) is not int:
        reject("invalid_envelope_timestamp")
    if expires != created + TTL or created > now + 300 or expires <= now:
        reject("envelope_expired_or_future")
    nonce = unb64(envelope["nonce_b64"], 12)
    sealed_key = unb64(envelope["sealed_key_b64"], 384)
    ciphertext = unb64(envelope["ciphertext_b64"], SQLITE_BYTES + 16)
    if len(nonce) != 12 or len(sealed_key) != 384 or len(ciphertext) != SQLITE_BYTES + 16:
        reject("invalid_envelope_lengths")
    try:
        aes_key = private_key.decrypt(sealed_key, oaep())
        if len(aes_key) != 32:
            reject("invalid_sealed_key")
        data = AESGCM(aes_key).decrypt(nonce, ciphertext, canonical(header))
    except (InvalidTag, ValueError):
        reject("envelope_authentication_failed")
    return data, verify_sqlite(data)


def no_reparse(path: Path) -> None:
    for ancestor in (path, *path.parents):
        if ancestor.exists():
            if ancestor.is_symlink() or (
                getattr(ancestor.stat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
            ):
                reject("private_path_reparse_rejected")


_WINDOWS_DLL_HANDLES: dict[str, object] = {}


def migration_dependency_site() -> Path | None:
    """Only this workflow's fixed temporary installation can extend DLL search."""
    raw_migration = os.environ.get("REQSYS_MIGRATION_DEPENDENCIES", "")
    raw_portable = os.environ.get("REQSYS_PYTHON_SITE", "")
    if not raw_migration and not raw_portable:
        return None  # Hosted Windows CI installs pywin32 normally.
    temporary = os.environ.get("RUNNER_TEMP", "")
    run = os.environ.get("GITHUB_RUN_ID", "")
    if not temporary or not Path(temporary).is_absolute() or not re.fullmatch(r"[1-9][0-9]*", run):
        reject("migration_dependency_correlation_invalid")
    base = Path(temporary).resolve()
    if raw_migration:
        requested = Path(raw_migration)
        expected = base / ("reqsys-migration-python-" + run)
    else:
        job = os.environ.get("GITHUB_JOB", "")
        attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", job) or not re.fullmatch(r"[1-9][0-9]*", attempt):
            reject("migration_dependency_correlation_invalid")
        requested = Path(raw_portable)
        expected = base / ("reqsys-python-3.12.10-" + job + "-" + run + "-" + attempt) / "Lib" / "site-packages"
    if not requested.is_absolute():
        reject("migration_dependency_path_not_fixed")
    no_reparse(requested)
    if requested.resolve() != expected.resolve():
        reject("migration_dependency_path_not_fixed")
    if not requested.is_dir():
        reject("migration_dependency_directory_missing")
    return requested.resolve()


def initialize_windows_libraries() -> None:
    if os.name != "nt":
        reject("windows_libraries_required")
    site = migration_dependency_site()
    if site is None:
        return
    import sys
    allowed = (site, site / "win32", site / "win32" / "lib")
    dll_directory = site / "pywin32_system32"
    for path in (*allowed, dll_directory):
        no_reparse(path)
        if not path.is_dir():
            reject("migration_pywin32_layout_missing")
    dll_key = str(dll_directory)
    if dll_key not in _WINDOWS_DLL_HANDLES:
        _WINDOWS_DLL_HANDLES[dll_key] = os.add_dll_directory(dll_key)
    # Avoid executing .pth files; only known pywin32 package directories are added.
    for path in reversed(allowed):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)


def private_scope_directory(path: Path) -> None:
    """Protect the dedicated task scope; shared ReqSys parent is never modified."""
    initialize_windows_libraries()
    import win32api
    import win32con
    import win32security
    no_reparse(path)
    if path.exists():
        if not path.is_dir():
            reject("private_scope_directory_required")
        token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32con.TOKEN_QUERY)
        try:
            user = win32security.GetTokenInformation(token, win32security.TokenUser)[0]
        finally:
            token.Close()
        system = win32security.CreateWellKnownSid(win32security.WinLocalSystemSid, None)
        administrators = win32security.CreateWellKnownSid(win32security.WinBuiltinAdministratorsSid, None)
        creator_owner = win32security.CreateWellKnownSid(win32security.WinCreatorOwnerSid, None)
        descriptor = win32security.GetFileSecurity(str(path),
            win32security.OWNER_SECURITY_INFORMATION | win32security.DACL_SECURITY_INFORMATION)
        owner = descriptor.GetSecurityDescriptorOwner()
        if owner not in (user, system, administrators):
            reject("private_scope_owner_untrusted")
        dacl = descriptor.GetSecurityDescriptorDacl()
        if dacl is None:
            reject("private_scope_acl_missing")
        protected = bool(descriptor.GetSecurityDescriptorControl()[0] & 0x1000)
        trusted = (user, system) if protected else (user, system, administrators, creator_owner)
        for index in range(dacl.GetAceCount()):
            ace = dacl.GetAce(index)
            if len(ace) != 3 or ace[0][0] != win32security.ACCESS_ALLOWED_ACE_TYPE or ace[2] not in trusted:
                reject("private_scope_acl_untrusted")
    else:
        path.mkdir(parents=True, exist_ok=False)
    secure_acl(path, directory=True)


def secure_acl(path: Path, *, directory: bool) -> None:
    """Private owner+SYSTEM DACL; no subprocess and no elevation."""
    initialize_windows_libraries()
    import win32api
    import win32con
    import win32security
    token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32con.TOKEN_QUERY)
    try:
        user_sid = win32security.GetTokenInformation(token, win32security.TokenUser)[0]
    finally:
        token.Close()
    system_sid = win32security.CreateWellKnownSid(win32security.WinLocalSystemSid, None)
    acl = win32security.ACL()
    flags = (win32con.OBJECT_INHERIT_ACE | win32con.CONTAINER_INHERIT_ACE) if directory else 0
    for sid in (user_sid, system_sid):
        acl.AddAccessAllowedAceEx(win32security.ACL_REVISION, flags, 0x1F01FF, sid)
    descriptor = win32security.SECURITY_DESCRIPTOR()
    descriptor.SetSecurityDescriptorDacl(1, acl, 0)
    # SetFileSecurity is a legacy API: the descriptor control must explicitly
    # protect the DACL; the SECURITY_INFORMATION flag alone is insufficient.
    descriptor.SetSecurityDescriptorControl(0x1000, 0x1000)
    win32security.SetFileSecurity(str(path),
        win32security.DACL_SECURITY_INFORMATION | win32security.PROTECTED_DACL_SECURITY_INFORMATION,
        descriptor)
    written = win32security.GetFileSecurity(str(path), win32security.DACL_SECURITY_INFORMATION)
    if not written.GetSecurityDescriptorControl()[0] & 0x1000:
        reject("private_acl_protection_not_applied")
    written_acl = written.GetSecurityDescriptorDacl()
    if written_acl is None or written_acl.GetAceCount() != 2:
        reject("private_acl_not_exclusive")
    expected_sids = {win32security.ConvertSidToStringSid(sid) for sid in (user_sid, system_sid)}
    observed_sids = set()
    for index in range(written_acl.GetAceCount()):
        ace = written_acl.GetAce(index)
        if (len(ace) != 3 or ace[0] != (win32security.ACCESS_ALLOWED_ACE_TYPE, flags)
                or ace[1] != 0x1F01FF):
            reject("private_acl_rights_or_flags_invalid")
        observed_sids.add(win32security.ConvertSidToStringSid(ace[2]))
    if observed_sids != expected_sids:
        reject("private_acl_identity_not_exclusive")


def receiver_root() -> Path:
    exact_host(TARGET_HOST)
    base = os.environ.get("LOCALAPPDATA", "")
    if not base or not Path(base).is_absolute():
        reject("localappdata_required")
    scope = Path(base) / "ReqSys" / "SelfHostedDev"
    private_scope_directory(scope)
    root = scope / "Migration"
    private_scope_directory(root)
    return root


def private_write(path: Path, value: bytes) -> None:
    no_reparse(path)
    temporary = path.with_name(path.name + ".new")
    no_reparse(temporary)
    if temporary.exists():
        reject("private_temporary_file_already_exists")
    try:
        with temporary.open("xb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        secure_acl(temporary, directory=False)
        # Caller refuses unexpected existing destinations; os.replace is atomic.
        os.replace(temporary, path)
        secure_acl(path, directory=False)
    finally:
        if temporary.exists():
            temporary.unlink()


def receiver_identity() -> tuple[rsa.RSAPrivateKey, dict]:
    """Idempotent key provisioning. Private key persists only inside user DPAPI."""
    exact_host(TARGET_HOST)
    initialize_windows_libraries()
    import win32crypt
    root = receiver_root()
    key_file, public_file = root / "receiver-private-key.dpapi", root / "receiver-public-key.json"
    if key_file.exists() != public_file.exists():
        reject("recipient_identity_partial")
    if key_file.exists():
        no_reparse(key_file)
        no_reparse(public_file)
        secure_acl(key_file, directory=False)
        secure_acl(public_file, directory=False)
        try:
            raw = win32crypt.CryptUnprotectData(key_file.read_bytes(), DPAPI_ENTROPY, None, None, 1)[1]
            key = serialization.load_der_private_key(raw, password=None)
            config = json.loads(public_file.read_bytes())
        except Exception:
            reject("recipient_identity_unprotect_failed")
    else:
        key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        raw = key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption())
        protected = win32crypt.CryptProtectData(raw, SCHEMA, DPAPI_ENTROPY, None, None, 1)
        config = {"schema": SCHEMA, "target_host": TARGET_HOST,
                  "public_key_der_b64": b64(public_der(key.public_key())),
                  "recipient_sha256": digest(public_der(key.public_key()))}
        private_write(key_file, protected)
        private_write(public_file, canonical(config))
    if not isinstance(key, rsa.RSAPrivateKey) or key.key_size != 3072:
        reject("recipient_private_key_type_mismatch")
    if config != {"schema": SCHEMA, "target_host": TARGET_HOST,
                  "public_key_der_b64": b64(public_der(key.public_key())),
                  "recipient_sha256": digest(public_der(key.public_key()))}:
        reject("recipient_identity_mismatch")
    return key, config


def reviewed_recipient(config: dict, pinned_sha256: str) -> rsa.RSAPublicKey:
    """Source receives the public configuration pinned by the PC provisioning evidence."""
    if not isinstance(config, dict) or set(config) != {
            "schema", "target_host", "public_key_der_b64", "recipient_sha256"}:
        reject("invalid_recipient_config")
    if config["schema"] != SCHEMA or config["target_host"] != TARGET_HOST:
        reject("recipient_context_mismatch")
    raw = unb64(config["public_key_der_b64"], 1024)
    if config["recipient_sha256"] != pinned_sha256 or digest(raw) != pinned_sha256:
        reject("recipient_public_key_not_pinned")
    try:
        key = serialization.load_der_public_key(raw)
    except (ValueError, TypeError):
        reject("invalid_recipient_public_key")
    public_der(key)
    return key


def restore_on_receiver(envelope_bytes: bytes, *, expected_run_id: int,
                        expected_source_sha: str, expected_envelope_sha256: str) -> dict:
    key, _ = receiver_identity()
    data, report = open_sqlite(envelope_bytes, key, expected_run_id=expected_run_id,
        expected_source_sha=expected_source_sha, expected_envelope_sha256=expected_envelope_sha256)
    destination = receiver_root() / "restored-dev.sqlite"
    no_reparse(destination)
    if destination.exists():
        if not hmac.compare_digest(digest(destination.read_bytes()), SQLITE_SHA256):
            reject("existing_restore_must_not_be_overwritten")
        secure_acl(destination, directory=False)
    else:
        private_write(destination, data)
    verify_sqlite(destination.read_bytes())
    return {**report, "ok": True, "source_host": SOURCE_HOST, "target_host": TARGET_HOST,
            "snapshot_id": SNAPSHOT_ID, "envelope_sha256": expected_envelope_sha256,
            "source_run_id": expected_run_id, "source_sha": expected_source_sha,
            "restored_destination": "Migration/restored-dev.sqlite",
            "artifact_plaintext": False, "production_touched": False, "fly_used": False}

BACKUP_ROOT = Path(r"C:\Users\erics\AppData\Local\ReqSys\MigrationBackups\20261002-1912")


def backup_metadata() -> dict:
    exact_host(SOURCE_HOST)
    no_reparse(BACKUP_ROOT)
    files = {}
    for relative in ("restic-password", "restic-repository/config",
                     "reqsys-dev-manifest.json", "encrypted-backup-evidence.json"):
        path = BACKUP_ROOT / relative
        no_reparse(path)
        files[relative] = {"exists": path.is_file(),
                           "bytes": path.stat().st_size if path.is_file() else None}
    return {"ok": BACKUP_ROOT.is_dir(), "source_host": SOURCE_HOST,
            "snapshot_id": SNAPSHOT_ID, "files": files,
            "file_contents_read": False, "password_exported": False}


RESTIC_VERSION = "0.18.0"
RESTIC_ZIP_URL = "https://github.com/restic/restic/releases/download/v0.18.0/restic_0.18.0_windows_amd64.zip"
RESTIC_ZIP_SHA256 = "c90cfcd577fe3d60d2529021e76bd5637bdcd19d7fa84840a40fcbbf995902de"
RESTIC_ZIP_BYTES = 10855338
RESTIC_ZIP_MEMBER = "restic_0.18.0_windows_amd64.exe"
MAX_RESTIC_EXE_BYTES = 80_000_000
RECIPIENT_RELATIVE = Path("config") / "self-hosted-dev-migration-recipient.json"


def restic_exe_from_verified_zip(package: bytes) -> bytes:
    import io
    import zipfile
    if len(package) != RESTIC_ZIP_BYTES or not hmac.compare_digest(digest(package), RESTIC_ZIP_SHA256):
        reject("restic_package_checksum_mismatch")
    try:
        with zipfile.ZipFile(io.BytesIO(package)) as archive:
            matches = [entry for entry in archive.infolist() if entry.filename == RESTIC_ZIP_MEMBER]
            if len(matches) != 1:
                reject("restic_executable_member_missing_or_duplicate")
            entry = matches[0]
            if entry.is_dir() or entry.flag_bits & 1 or not 0 < entry.file_size <= MAX_RESTIC_EXE_BYTES:
                reject("restic_executable_member_invalid")
            # Never extractall: only the exact official executable is read.
            executable = archive.read(entry)
    except (zipfile.BadZipFile, RuntimeError) as exc:
        if isinstance(exc, TransportError):
            raise
        reject("restic_package_archive_invalid")
    if len(executable) > MAX_RESTIC_EXE_BYTES or not executable.startswith(b"MZ"):
        reject("restic_executable_header_invalid")
    return executable


def download_fixed_restic_package() -> bytes:
    import urllib.request
    from urllib.parse import urlsplit

    class OfficialReleaseRedirect(urllib.request.HTTPRedirectHandler):
        redirects = 0
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            parsed = urlsplit(newurl)
            self.redirects += 1
            if (self.redirects > 3 or parsed.scheme != "https" or
                    parsed.hostname not in {"github.com", "release-assets.githubusercontent.com",
                                            "objects.githubusercontent.com"} or
                    parsed.username is not None or parsed.password is not None or
                    parsed.port not in (None, 443)):
                reject("restic_download_redirect_rejected")
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    request = urllib.request.Request(RESTIC_ZIP_URL, headers={
        "User-Agent": "ReqSysFixedDevBackupTransport/1",
        "Accept": "application/octet-stream",
    })
    try:
        opener = urllib.request.build_opener(OfficialReleaseRedirect())
        with opener.open(request, timeout=120) as response:
            if response.status != 200:
                reject("restic_download_http_failed")
            length = response.headers.get("Content-Length")
            if length is not None and length != str(RESTIC_ZIP_BYTES):
                reject("restic_download_length_mismatch")
            package = response.read(RESTIC_ZIP_BYTES + 1)
    except TransportError:
        raise
    except Exception:
        reject("restic_fixed_download_failed")
    restic_exe_from_verified_zip(package)
    return package


def source_temp_root() -> Path:
    exact_host(SOURCE_HOST)
    raw = os.environ.get("RUNNER_TEMP", "")
    if not raw or not Path(raw).is_absolute():
        reject("runner_temp_required")
    root = Path(raw) / "reqsys-dev-backup-restic"
    no_reparse(root)
    root.mkdir(parents=True, exist_ok=True)
    no_reparse(root)
    secure_acl(root, directory=True)
    return root


def provision_restic() -> tuple[Path, dict]:
    root = source_temp_root()
    package_path = root / "restic-fixed.zip"
    no_reparse(package_path)
    if package_path.is_file():
        with package_path.open("rb") as stream:
            package = stream.read(RESTIC_ZIP_BYTES + 1)
    else:
        package = download_fixed_restic_package()
        private_write(package_path, package)
    executable = restic_exe_from_verified_zip(package)
    executable_path = root / "restic.exe"
    no_reparse(executable_path)
    exe_sha = digest(executable)
    if executable_path.exists():
        with executable_path.open("rb") as stream:
            installed = stream.read(MAX_RESTIC_EXE_BYTES + 1)
        if not hmac.compare_digest(digest(installed), exe_sha):
            reject("restic_installed_executable_mismatch")
        secure_acl(executable_path, directory=False)
    else:
        private_write(executable_path, executable)
    report = {"version": RESTIC_VERSION, "zip_sha256": RESTIC_ZIP_SHA256,
              "zip_bytes": RESTIC_ZIP_BYTES, "executable_sha256": exe_sha,
              "executable_bytes": len(executable), "global_path_changed": False}
    manifest_path = root / "restic-provision.json"
    if not manifest_path.exists() or manifest_path.read_bytes() != canonical(report):
        private_write(manifest_path, canonical(report))
    return executable_path, report


def safe_snapshot_path(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > 4096:
        reject("restic_snapshot_path_invalid")
    if any(ord(character) < 32 for character in value):
        reject("restic_snapshot_path_invalid")
    normalized = value.replace("\\", "/")
    if normalized.startswith("//") or ".." in normalized.split("/"):
        reject("restic_snapshot_path_invalid")
    if not (normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized)):
        reject("restic_snapshot_path_invalid")
    return value


def fixed_restic_call(executable: Path, operation: str, *, snapshot_path: str | None = None) -> bytes:
    import subprocess
    exact_host(SOURCE_HOST)
    for path in (BACKUP_ROOT, BACKUP_ROOT / "restic-repository", BACKUP_ROOT / "restic-password"):
        no_reparse(path)
    if not (BACKUP_ROOT / "restic-repository" / "config").is_file():
        reject("fixed_restic_repository_missing")
    if not (BACKUP_ROOT / "restic-password").is_file():
        reject("fixed_restic_password_file_missing")
    # Explicit fixed files; never inherit a password/password-command/repository override.
    environment = dict(os.environ)
    for name in tuple(environment):
        if name.startswith("RESTIC_"):
            environment.pop(name)
    command = [str(executable), "--no-cache", "--no-lock", "--repo",
               str(BACKUP_ROOT / "restic-repository"), "--password-file",
               str(BACKUP_ROOT / "restic-password")]
    if operation == "inventory":
        command += ["ls", "--json", SNAPSHOT_ID]
        maximum = 1_000_000
    elif operation == "dump" and snapshot_path is not None:
        command += ["dump", SNAPSHOT_ID, safe_snapshot_path(snapshot_path)]
        maximum = SQLITE_BYTES
    else:
        reject("restic_operation_not_allowlisted")
    try:
        completed = subprocess.run(command, cwd=str(BACKUP_ROOT), env=environment,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=120, check=False, shell=False)
    except (OSError, subprocess.TimeoutExpired):
        reject("restic_fixed_operation_unavailable")
    if completed.returncode != 0:
        reject("restic_fixed_operation_failed")
    if len(completed.stdout) > maximum:
        reject("restic_fixed_output_too_large")
    return completed.stdout


def parse_snapshot_inventory(data: bytes) -> list[dict]:
    if len(data) > 1_000_000:
        reject("restic_inventory_too_large")
    files, snapshot_seen = [], False
    lines = data.splitlines()
    if len(lines) > 1000:
        reject("restic_inventory_too_many_nodes")
    for line in lines:
        if not line.strip():
            continue
        try:
            node = json.loads(line)
        except (ValueError, UnicodeError):
            reject("restic_inventory_json_invalid")
        if not isinstance(node, dict):
            reject("restic_inventory_node_invalid")
        if node.get("struct_type") == "snapshot":
            if node.get("id") != SNAPSHOT_ID:
                reject("restic_snapshot_identity_mismatch")
            snapshot_seen = True
        elif node.get("struct_type") == "node" and node.get("type") == "file":
            path = safe_snapshot_path(node.get("path"))
            size = node.get("size")
            if type(size) is not int or size < 0:
                reject("restic_inventory_size_invalid")
            files.append({"snapshot_path": path, "bytes": size})
    if not snapshot_seen:
        reject("restic_snapshot_header_missing")
    return sorted(files, key=lambda item: item["snapshot_path"])


def inventory_on_source() -> dict:
    executable, package = provision_restic()
    files = parse_snapshot_inventory(fixed_restic_call(executable, "inventory"))
    return {"ok": True, "source_host": SOURCE_HOST, "snapshot_id": SNAPSHOT_ID,
            "restic": package, "snapshot_files": files, "database_contents_read": False,
            "password_exported": False, "production_touched": False, "fly_used": False}


def selected_sqlite_path(files: list[dict]) -> str:
    matches = [item["snapshot_path"] for item in files if item["bytes"] == SQLITE_BYTES
               and item["snapshot_path"].lower().endswith((".sqlite", ".sqlite3", ".db"))]
    if len(matches) != 1:
        reject("fixed_sqlite_snapshot_candidate_missing_or_ambiguous")
    return matches[0]


def seal_on_source(recipient_file: str, recipient_sha256: str,
                   source_run_id: int, source_sha: str) -> dict:
    exact_host(SOURCE_HOST)
    if not re.fullmatch(r"[0-9a-f]{64}", recipient_sha256):
        reject("invalid_recipient_pin")
    expected_recipient = Path(__file__).resolve().parents[1] / RECIPIENT_RELATIVE
    requested_recipient = Path(recipient_file)
    no_reparse(expected_recipient)
    if requested_recipient.resolve() != expected_recipient.resolve():
        reject("fixed_recipient_config_path_required")
    try:
        with expected_recipient.open("rb") as stream:
            encoded_config = stream.read(8193)
        if len(encoded_config) > 8192:
            reject("recipient_config_too_large")
        config = json.loads(encoded_config)
    except (OSError, ValueError, UnicodeError):
        reject("recipient_config_unavailable")
    public_key = reviewed_recipient(config, recipient_sha256)
    executable, package = provision_restic()
    files = parse_snapshot_inventory(fixed_restic_call(executable, "inventory"))
    snapshot_path = selected_sqlite_path(files)
    data = fixed_restic_call(executable, "dump", snapshot_path=snapshot_path)
    report = verify_sqlite(data)
    envelope = seal_sqlite(data, public_key, source_run_id, source_sha)
    destination = source_temp_root() / "envelope.json"
    if destination.exists():
        # A fresh nonce and timestamp are necessary after expiry; source data never changes.
        no_reparse(destination)
    private_write(destination, envelope)
    return {**report, "ok": True, "source_host": SOURCE_HOST, "target_host": TARGET_HOST,
            "snapshot_id": SNAPSHOT_ID, "snapshot_path": snapshot_path,
            "restic": package, "recipient_sha256": recipient_sha256,
            "source_run_id": source_run_id, "source_sha": source_sha,
            "envelope_sha256": digest(envelope), "envelope_bytes": len(envelope),
            "artifact_relative": "reqsys-dev-backup-restic/envelope.json",
            "artifact_plaintext": False, "password_exported": False,
            "private_key_exported": False, "production_touched": False, "fly_used": False}

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser("recipient-init").add_argument("--confirm", required=True)
    actions.add_parser("backup-metadata").add_argument("--confirm", required=True)
    actions.add_parser("restic-inventory").add_argument("--confirm", required=True)
    seal = actions.add_parser("seal")
    seal.add_argument("--confirm", required=True)
    seal.add_argument("--recipient-file", required=True)
    seal.add_argument("--recipient-sha256", required=True)
    seal.add_argument("--source-run-id", type=int, required=True)
    seal.add_argument("--source-sha", required=True)
    receive = actions.add_parser("receive")
    receive.add_argument("--confirm", required=True)
    receive.add_argument("--source-run-id", type=int, required=True)
    receive.add_argument("--source-sha", required=True)
    receive.add_argument("--envelope-sha256", required=True)
    args = parser.parse_args()
    try:
        if args.action == "recipient-init":
            if args.confirm != "INIT-PC24X7-DEV-MIGRATION-IDENTITY":
                reject("fixed_confirmation_required")
            _, public = receiver_identity()
            result = {"ok": True, "target_host": TARGET_HOST, "public_recipient": public,
                      "private_key_exported": False, "production_touched": False}
        elif args.action == "backup-metadata":
            if args.confirm != "PROBE-NOTERI-DEV-MIGRATION-BACKUP":
                reject("fixed_confirmation_required")
            result = backup_metadata()
        elif args.action == "restic-inventory":
            if args.confirm != "INVENTORY-NOTERI-FIXED-RESTIC-DEV-BACKUP":
                reject("fixed_confirmation_required")
            result = inventory_on_source()
        elif args.action == "seal":
            if args.confirm != "SEAL-NOTERI-DEV-BACKUP-FOR-PC24X7":
                reject("fixed_confirmation_required")
            result = seal_on_source(args.recipient_file, args.recipient_sha256,
                                    args.source_run_id, args.source_sha)
        else:
            if args.confirm != "RESTORE-PC24X7-SEALED-DEV-BACKUP":
                reject("fixed_confirmation_required")
            exact_host(TARGET_HOST)
            temporary_root = Path(os.environ.get("RUNNER_TEMP", ""))
            if not temporary_root.is_absolute():
                reject("runner_temp_required")
            envelope_path = temporary_root / "dev-backup-input" / "envelope.json"
            no_reparse(envelope_path)
            with envelope_path.open("rb") as stream:
                envelope = stream.read(MAX_ENVELOPE_BYTES + 1)
            result = restore_on_receiver(envelope, expected_run_id=args.source_run_id,
                expected_source_sha=args.source_sha, expected_envelope_sha256=args.envelope_sha256)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0 if result.get("ok") else 1
    except TransportError as exc:
        print(json.dumps({"ok": False, "code": str(exc)}, separators=(",", ":")))
        return 1
    except Exception as exc:
        print(json.dumps({"ok": False, "code": "transport_operation_failed",
                          "error_type": type(exc).__name__}, separators=(",", ":")))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
