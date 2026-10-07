"""Streaming, authenticated migration bundles from NOTERI to DESKTOP-PDQK954.

The command-line wrapper is deliberately host and path constrained.  The
cryptographic core is platform-independent so it can be regression-tested in
CI without accessing DPAPI or a real migration directory.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import socket
import stat
import struct
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO, Protocol

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

SCHEMA = "reqsys-noteri-desktop-bundle-v1"
LEGACY_RECIPIENT_SCHEMA = "reqsys-dev-noteri-pc24x7-backup-v1"
SOURCE_HOST = "NOTERI"
TARGET_HOST = "DESKTOP-PDQK954"
MAGIC = b"REQSYS-NOTERI-DESKTOP-BUNDLE-V1\x00"
OAEP_LABEL = SCHEMA.encode("ascii")
CHUNK_BYTES = 4 * 1024 * 1024
NONCE_BYTES = 12
TAG_BYTES = 16
WRAPPED_KEY_BYTES = 384
MAX_HEADER_BYTES = 16 * 1024
MAX_RECIPIENT_BYTES = 32 * 1024
# SP 800-38D, section 5.2.1.1: one GCM invocation accepts at most
# 2^39-256 plaintext bits.  Each bundle is exactly one GCM invocation.
MAX_PLAINTEXT_BYTES = (2**39 - 256) // 8
DEFAULT_TTL_SECONDS = 24 * 60 * 60
MIN_TTL_SECONDS = 60
MAX_TTL_SECONDS = 7 * 24 * 60 * 60
MAX_CLOCK_SKEW_SECONDS = 5 * 60
HEADER_FIELDS = {
    "cipher",
    "created_at",
    "expires_at",
    "key_wrap",
    "plaintext_bytes",
    "plaintext_sha256",
    "recipient_sha256",
    "schema",
    "source_host",
    "target_host",
}


class BundleTransportError(RuntimeError):
    """A failure represented only by a stable, non-sensitive code."""


class _DigestState(Protocol):
    def update(self, value: bytes) -> None: ...


def reject(code: str) -> None:
    raise BundleTransportError(code)


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def public_der(key: rsa.RSAPublicKey) -> bytes:
    if (
        not isinstance(key, rsa.RSAPublicKey)
        or key.key_size != 3072
        or key.public_numbers().e != 65537
    ):
        reject("recipient_rsa_3072_required")
    return key.public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def recipient_fingerprint(key: rsa.RSAPublicKey) -> str:
    return sha256_bytes(public_der(key))


def oaep() -> padding.OAEP:
    return padding.OAEP(
        mgf=padding.MGF1(hashes.SHA256()),
        algorithm=hashes.SHA256(),
        label=OAEP_LABEL,
    )


def _validate_ttl(ttl_seconds: int) -> int:
    if (
        isinstance(ttl_seconds, bool)
        or not isinstance(ttl_seconds, int)
        or not MIN_TTL_SECONDS <= ttl_seconds <= MAX_TTL_SECONDS
    ):
        reject("ttl_out_of_range")
    return ttl_seconds


def _validate_now(now: int | None) -> int:
    value = int(time.time()) if now is None else now
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        reject("invalid_timestamp")
    return value


def _file_digest(stream: BinaryIO) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    while True:
        block = stream.read(CHUNK_BYTES)
        if not block:
            break
        total += len(block)
        if total > MAX_PLAINTEXT_BYTES:
            reject("plaintext_too_large")
        digest.update(block)
    return digest.hexdigest(), total


def _default_harden_file(path: Path) -> None:
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        reject("private_permissions_failed")


def _new_private_temp(destination: Path) -> tuple[Path, BinaryIO]:
    descriptor: int | None = None
    path: Path | None = None
    try:
        descriptor, raw_path = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".partial", dir=destination.parent
        )
        path = Path(raw_path)
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        stream = os.fdopen(descriptor, "w+b", buffering=0)
        descriptor = None  # Ownership moved to the file object.
        return path, stream
    except OSError:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if path is not None:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        reject("private_temporary_file_failed")


def _publish_no_replace(
    temporary: Path,
    destination: Path,
    harden_file: Callable[[Path], None],
) -> None:
    if destination.exists():
        reject("destination_already_exists")
    try:
        harden_file(temporary)
        # A hard link publishes a completely flushed inode and fails atomically
        # if the destination appeared concurrently.  Both names are in the
        # same directory/filesystem.
        os.link(temporary, destination, follow_symlinks=False)
    except FileExistsError:
        reject("destination_already_exists")
    except BundleTransportError:
        raise
    except OSError:
        reject("atomic_publish_failed")
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _write_exact(stream: BinaryIO, value: bytes, code: str) -> None:
    try:
        written = stream.write(value)
    except OSError:
        reject(code)
    if written != len(value):
        reject(code)


def _write_and_hash(stream: BinaryIO, value: bytes, digest: _DigestState) -> None:
    _write_exact(stream, value, "envelope_write_failed")
    digest.update(value)


def _regular_file(stream: BinaryIO, *, code: str) -> os.stat_result:
    try:
        metadata = os.fstat(stream.fileno())
    except OSError:
        reject(code)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        reject(code)
    return metadata


def seal_file(
    source: Path,
    destination: Path,
    recipient: rsa.RSAPublicKey,
    *,
    now: int | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    source_host: str = SOURCE_HOST,
    target_host: str = TARGET_HOST,
    harden_file: Callable[[Path], None] = _default_harden_file,
) -> dict:
    """Seal one regular file using constant-memory AES-256-GCM streaming."""
    recipient_sha256 = recipient_fingerprint(recipient)
    created_at = _validate_now(now)
    ttl_seconds = _validate_ttl(ttl_seconds)
    if source_host != SOURCE_HOST or target_host != TARGET_HOST:
        reject("host_binding_invalid")
    if destination.exists():
        reject("destination_already_exists")

    temporary: Path | None = None
    try:
        try:
            plaintext = source.open("rb")
        except OSError:
            reject("source_file_unavailable")
        with plaintext:
            initial_stat = _regular_file(plaintext, code="source_regular_file_required")
            plaintext_sha256, plaintext_bytes = _file_digest(plaintext)
            if plaintext_bytes != initial_stat.st_size:
                reject("source_changed_during_seal")
            plaintext.seek(0)

            header = {
                "cipher": "AES-256-GCM",
                "created_at": created_at,
                "expires_at": created_at + ttl_seconds,
                "key_wrap": "RSA-3072-OAEP-SHA256",
                "plaintext_bytes": plaintext_bytes,
                "plaintext_sha256": plaintext_sha256,
                "recipient_sha256": recipient_sha256,
                "schema": SCHEMA,
                "source_host": SOURCE_HOST,
                "target_host": TARGET_HOST,
            }
            header_bytes = canonical(header)
            if len(header_bytes) > MAX_HEADER_BYTES:
                reject("header_too_large")

            aes_key = os.urandom(32)
            nonce = os.urandom(NONCE_BYTES)
            try:
                wrapped_key = recipient.encrypt(aes_key, oaep())
            except ValueError:
                reject("recipient_key_wrap_failed")
            if len(wrapped_key) != WRAPPED_KEY_BYTES:
                reject("wrapped_key_length_invalid")

            temporary, envelope = _new_private_temp(destination)
            envelope_digest = hashlib.sha256()
            with envelope:
                for part in (
                    MAGIC,
                    struct.pack(">I", len(header_bytes)),
                    header_bytes,
                    struct.pack(">H", len(wrapped_key)),
                    wrapped_key,
                    nonce,
                ):
                    _write_and_hash(envelope, part, envelope_digest)

                encryptor = Cipher(
                    algorithms.AES(aes_key), modes.GCM(nonce)
                ).encryptor()
                encryptor.authenticate_additional_data(header_bytes)
                second_digest = hashlib.sha256()
                second_size = 0
                while True:
                    block = plaintext.read(CHUNK_BYTES)
                    if not block:
                        break
                    second_digest.update(block)
                    second_size += len(block)
                    _write_and_hash(envelope, encryptor.update(block), envelope_digest)
                final_ciphertext = encryptor.finalize()
                if final_ciphertext:
                    _write_and_hash(envelope, final_ciphertext, envelope_digest)
                _write_and_hash(envelope, encryptor.tag, envelope_digest)

                final_stat = os.fstat(plaintext.fileno())
                if (
                    second_size != plaintext_bytes
                    or not hmac.compare_digest(
                        second_digest.hexdigest(), plaintext_sha256
                    )
                    or final_stat.st_size != initial_stat.st_size
                    or final_stat.st_mtime_ns != initial_stat.st_mtime_ns
                ):
                    reject("source_changed_during_seal")
                envelope.flush()
                os.fsync(envelope.fileno())

        envelope_bytes = temporary.stat().st_size
        _publish_no_replace(temporary, destination, harden_file)
        temporary = None
        return {
            "ok": True,
            "schema": SCHEMA,
            "source_host": SOURCE_HOST,
            "target_host": TARGET_HOST,
            "plaintext_sha256": plaintext_sha256,
            "plaintext_bytes": plaintext_bytes,
            "recipient_sha256": recipient_sha256,
            "created_at": created_at,
            "expires_at": created_at + ttl_seconds,
            "envelope_sha256": envelope_digest.hexdigest(),
            "envelope_bytes": envelope_bytes,
        }
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def _read_exact(stream: BinaryIO, size: int, code: str = "envelope_truncated") -> bytes:
    if size < 0:
        reject("invalid_envelope_length")
    value = stream.read(size)
    if len(value) != size:
        reject(code)
    return value


def _read_and_hash(
    stream: BinaryIO, size: int, digest: _DigestState, code: str = "envelope_truncated"
) -> bytes:
    value = _read_exact(stream, size, code)
    digest.update(value)
    return value


def _decode_header(encoded: bytes, private_key: rsa.RSAPrivateKey, now: int) -> dict:
    try:
        header = json.loads(encoded)
    except (UnicodeError, ValueError):
        reject("invalid_header_json")
    if not isinstance(header, dict) or set(header) != HEADER_FIELDS:
        reject("invalid_header_schema")
    if not hmac.compare_digest(canonical(header), encoded):
        reject("header_not_canonical")

    expected_strings = {
        "cipher": "AES-256-GCM",
        "key_wrap": "RSA-3072-OAEP-SHA256",
        "schema": SCHEMA,
        "source_host": SOURCE_HOST,
        "target_host": TARGET_HOST,
        "recipient_sha256": recipient_fingerprint(private_key.public_key()),
    }
    for name, expected in expected_strings.items():
        if not isinstance(header[name], str) or not hmac.compare_digest(
            header[name], expected
        ):
            if name == "recipient_sha256":
                reject("recipient_fingerprint_mismatch")
            reject("header_binding_mismatch")

    plaintext_sha256 = header["plaintext_sha256"]
    if not isinstance(plaintext_sha256, str) or not re.fullmatch(
        r"[0-9a-f]{64}", plaintext_sha256
    ):
        reject("invalid_plaintext_digest")
    plaintext_bytes = header["plaintext_bytes"]
    if (
        isinstance(plaintext_bytes, bool)
        or not isinstance(plaintext_bytes, int)
        or not 0 <= plaintext_bytes <= MAX_PLAINTEXT_BYTES
    ):
        reject("invalid_plaintext_size")
    created_at, expires_at = header["created_at"], header["expires_at"]
    if (
        isinstance(created_at, bool)
        or isinstance(expires_at, bool)
        or not isinstance(created_at, int)
        or not isinstance(expires_at, int)
        or created_at < 0
    ):
        reject("invalid_envelope_timestamp")
    lifespan = expires_at - created_at
    _validate_ttl(lifespan)
    if created_at > now + MAX_CLOCK_SKEW_SECONDS or expires_at <= now:
        reject("envelope_expired_or_future")
    return header


def receive_file(
    source: Path,
    destination: Path,
    private_key: rsa.RSAPrivateKey,
    *,
    expected_envelope_sha256: str,
    expected_plaintext_sha256: str,
    expected_plaintext_bytes: int,
    now: int | None = None,
    harden_file: Callable[[Path], None] = _default_harden_file,
) -> dict:
    """Authenticate and decrypt a bundle, publishing plaintext only on success."""
    if (
        not isinstance(private_key, rsa.RSAPrivateKey)
        or private_key.key_size != 3072
        or private_key.public_key().public_numbers().e != 65537
    ):
        reject("recipient_rsa_3072_required")
    if not isinstance(expected_envelope_sha256, str) or not re.fullmatch(
        r"[0-9a-f]{64}", expected_envelope_sha256
    ):
        reject("invalid_expected_envelope_digest")
    if not isinstance(expected_plaintext_sha256, str) or not re.fullmatch(
        r"[0-9a-f]{64}", expected_plaintext_sha256
    ):
        reject("invalid_expected_plaintext_digest")
    if (
        isinstance(expected_plaintext_bytes, bool)
        or not isinstance(expected_plaintext_bytes, int)
        or not 0 <= expected_plaintext_bytes <= MAX_PLAINTEXT_BYTES
    ):
        reject("invalid_expected_plaintext_size")
    received_at = _validate_now(now)
    if destination.exists():
        reject("destination_already_exists")

    temporary: Path | None = None
    try:
        try:
            envelope = source.open("rb")
        except OSError:
            reject("envelope_file_unavailable")
        with envelope:
            envelope_stat = _regular_file(
                envelope, code="envelope_regular_file_required"
            )
            maximum_envelope_bytes = (
                len(MAGIC)
                + 4
                + MAX_HEADER_BYTES
                + 2
                + WRAPPED_KEY_BYTES
                + NONCE_BYTES
                + MAX_PLAINTEXT_BYTES
                + TAG_BYTES
            )
            if envelope_stat.st_size > maximum_envelope_bytes:
                reject("envelope_too_large")
            envelope_digest = hashlib.sha256()
            if _read_and_hash(envelope, len(MAGIC), envelope_digest) != MAGIC:
                reject("invalid_envelope_magic")
            header_size = struct.unpack(
                ">I", _read_and_hash(envelope, 4, envelope_digest)
            )[0]
            if not 1 <= header_size <= MAX_HEADER_BYTES:
                reject("invalid_header_length")
            header_bytes = _read_and_hash(envelope, header_size, envelope_digest)
            header = _decode_header(header_bytes, private_key, received_at)
            if (
                not hmac.compare_digest(
                    header["plaintext_sha256"], expected_plaintext_sha256
                )
                or header["plaintext_bytes"] != expected_plaintext_bytes
            ):
                reject("expected_plaintext_mismatch")
            wrapped_size = struct.unpack(
                ">H", _read_and_hash(envelope, 2, envelope_digest)
            )[0]
            if wrapped_size != WRAPPED_KEY_BYTES:
                reject("wrapped_key_length_invalid")
            wrapped_key = _read_and_hash(envelope, wrapped_size, envelope_digest)
            nonce = _read_and_hash(envelope, NONCE_BYTES, envelope_digest)
            ciphertext_offset = envelope.tell()
            expected_bytes = ciphertext_offset + header["plaintext_bytes"] + TAG_BYTES
            if envelope_stat.st_size < expected_bytes:
                reject("envelope_truncated")
            if envelope_stat.st_size > expected_bytes:
                reject("envelope_length_mismatch")

            try:
                aes_key = private_key.decrypt(wrapped_key, oaep())
            except ValueError:
                reject("envelope_key_unwrap_failed")
            if len(aes_key) != 32:
                reject("invalid_unwrapped_key")

            temporary, plaintext = _new_private_temp(destination)
            plaintext_digest = hashlib.sha256()
            plaintext_size = 0
            with plaintext:
                decryptor = Cipher(
                    algorithms.AES(aes_key),
                    modes.GCM(nonce, min_tag_length=TAG_BYTES),
                ).decryptor()
                decryptor.authenticate_additional_data(header_bytes)
                remaining = header["plaintext_bytes"]
                while remaining:
                    block = _read_and_hash(
                        envelope, min(CHUNK_BYTES, remaining), envelope_digest
                    )
                    remaining -= len(block)
                    cleartext = decryptor.update(block)
                    try:
                        written = plaintext.write(cleartext)
                    except OSError:
                        reject("plaintext_write_failed")
                    if written != len(cleartext):
                        reject("plaintext_write_failed")
                    plaintext_digest.update(cleartext)
                    plaintext_size += len(cleartext)
                tag = _read_and_hash(envelope, TAG_BYTES, envelope_digest)
                if not hmac.compare_digest(
                    envelope_digest.hexdigest(), expected_envelope_sha256
                ):
                    reject("artifact_digest_mismatch")
                try:
                    cleartext = decryptor.finalize_with_tag(tag)
                except InvalidTag:
                    reject("envelope_authentication_failed")
                if cleartext:
                    try:
                        written = plaintext.write(cleartext)
                    except OSError:
                        reject("plaintext_write_failed")
                    if written != len(cleartext):
                        reject("plaintext_write_failed")
                    plaintext_digest.update(cleartext)
                    plaintext_size += len(cleartext)
                if plaintext_size != header[
                    "plaintext_bytes"
                ] or not hmac.compare_digest(
                    plaintext_digest.hexdigest(), header["plaintext_sha256"]
                ):
                    reject("plaintext_integrity_mismatch")
                plaintext.flush()
                os.fsync(plaintext.fileno())

        _publish_no_replace(temporary, destination, harden_file)
        temporary = None
        return {
            "ok": True,
            "schema": SCHEMA,
            "source_host": SOURCE_HOST,
            "target_host": TARGET_HOST,
            "envelope_sha256": expected_envelope_sha256,
            "plaintext_sha256": header["plaintext_sha256"],
            "plaintext_bytes": header["plaintext_bytes"],
            "recipient_sha256": header["recipient_sha256"],
            "created_at": header["created_at"],
            "expires_at": header["expires_at"],
        }
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def load_recipient(data: bytes, pinned_sha256: str) -> rsa.RSAPublicKey:
    """Load a pinned RSA public key from the existing config, PEM, or DER."""
    if not re.fullmatch(r"[0-9a-f]{64}", pinned_sha256 or ""):
        reject("invalid_recipient_pin")
    if not data or len(data) > MAX_RECIPIENT_BYTES:
        reject("recipient_file_size_invalid")

    key: object
    if data.lstrip().startswith(b"{"):
        try:
            config = json.loads(data)
        except (UnicodeError, ValueError):
            reject("invalid_recipient_config")
        required = {
            "schema",
            "target_host",
            "public_key_der_b64",
            "recipient_sha256",
        }
        if not isinstance(config, dict) or set(config) != required:
            reject("invalid_recipient_config")
        if not all(isinstance(config[name], str) for name in required):
            reject("recipient_config_binding_mismatch")
        if (
            config["schema"] not in {SCHEMA, LEGACY_RECIPIENT_SCHEMA}
            or config["target_host"] != TARGET_HOST
            or config["recipient_sha256"] != pinned_sha256
        ):
            reject("recipient_config_binding_mismatch")
        try:
            der = base64.b64decode(config["public_key_der_b64"], validate=True)
            key = serialization.load_der_public_key(der)
        except (ValueError, TypeError):
            reject("invalid_recipient_public_key")
    else:
        try:
            if data.lstrip().startswith(b"-----BEGIN"):
                key = serialization.load_pem_public_key(data)
            else:
                key = serialization.load_der_public_key(data)
        except (ValueError, TypeError):
            reject("invalid_recipient_public_key")

    if not isinstance(key, rsa.RSAPublicKey):
        reject("invalid_recipient_public_key")
    observed = recipient_fingerprint(key)
    if not hmac.compare_digest(observed, pinned_sha256):
        reject("recipient_public_key_not_pinned")
    return key


def _legacy_transport():
    try:
        from scripts import dev_backup_transport
    except ImportError:
        import dev_backup_transport  # type: ignore[no-redef]
    return dev_backup_transport


def _windows_harden_file(path: Path) -> None:
    _legacy_transport().secure_acl(path, directory=False)


def _exact_windows_host(expected: str) -> None:
    if os.name != "nt" or socket.gethostname().casefold() != expected.casefold():
        reject("fixed_windows_host_required")


def _migration_root(expected_host: str) -> Path:
    _exact_windows_host(expected_host)
    import ctypes
    from ctypes import wintypes

    class Guid(ctypes.Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    folder_id = Guid(
        0xF1B32785,
        0x6FBA,
        0x4FCF,
        (ctypes.c_ubyte * 8)(0x9D, 0x55, 0x7B, 0x8E, 0x7F, 0x15, 0x70, 0x91),
    )
    path_pointer = ctypes.c_wchar_p()
    known_folder = ctypes.windll.shell32.SHGetKnownFolderPath
    known_folder.argtypes = [
        ctypes.POINTER(Guid),
        wintypes.DWORD,
        wintypes.HANDLE,
        ctypes.POINTER(ctypes.c_wchar_p),
    ]
    known_folder.restype = ctypes.c_long
    free_memory = ctypes.windll.ole32.CoTaskMemFree
    free_memory.argtypes = [ctypes.c_void_p]
    free_memory.restype = None
    drive_type = ctypes.windll.kernel32.GetDriveTypeW
    drive_type.argtypes = [wintypes.LPCWSTR]
    drive_type.restype = wintypes.UINT
    try:
        result = known_folder(
            ctypes.byref(folder_id), 0, None, ctypes.byref(path_pointer)
        )
        if result != 0 or not path_pointer.value:
            reject("localappdata_known_folder_unavailable")
        local_app_data = Path(path_pointer.value)
    finally:
        if path_pointer:
            free_memory(ctypes.cast(path_pointer, ctypes.c_void_p))
    raw_root = str(local_app_data)
    if (
        not local_app_data.is_absolute()
        or raw_root.startswith(("\\\\", "\\\\?\\", "\\\\.\\"))
        or drive_type(local_app_data.anchor) != 3
    ):
        reject("localappdata_must_be_local_fixed_drive")
    legacy = _legacy_transport()
    root = local_app_data / "ReqSys" / "NoteriMigration"
    legacy.no_reparse(root)
    legacy.private_scope_directory(root)
    return root.resolve()


def _path_under_root(
    raw: str,
    root: Path,
    *,
    require_file: bool,
    require_absent: bool = False,
) -> Path:
    if not raw or any(ord(character) < 32 for character in raw):
        reject("migration_path_invalid")
    requested = Path(raw)
    if not requested.is_absolute() or ".." in requested.parts:
        reject("migration_path_must_be_absolute")
    legacy = _legacy_transport()
    legacy.no_reparse(requested)
    try:
        resolved = requested.resolve(strict=False)
        if os.path.commonpath((str(root), str(resolved))) != str(root):
            reject("migration_path_outside_root")
    except (OSError, ValueError):
        reject("migration_path_outside_root")
    if resolved == root:
        reject("migration_file_path_required")

    relative_parent = resolved.parent.relative_to(root)
    current = root
    for part in relative_parent.parts:
        current /= part
        legacy.no_reparse(current)
        legacy.private_scope_directory(current)
    if require_file:
        try:
            metadata = resolved.stat(follow_symlinks=False)
        except OSError:
            reject("migration_input_file_required")
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            reject("migration_input_file_required")
    if require_absent and resolved.exists():
        reject("destination_already_exists")
    return resolved


def _read_recipient_file(path: Path, pin: str) -> rsa.RSAPublicKey:
    try:
        with path.open("rb") as stream:
            data = stream.read(MAX_RECIPIENT_BYTES + 1)
    except OSError:
        reject("recipient_file_unavailable")
    return load_recipient(data, pin)


def _relative_report_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)

    export = actions.add_parser("recipient-export")
    export.add_argument("--confirm", required=True)
    export.add_argument("--output", required=True)

    seal = actions.add_parser("seal")
    seal.add_argument("--confirm", required=True)
    seal.add_argument("--input", required=True)
    seal.add_argument("--output", required=True)
    recipient = seal.add_mutually_exclusive_group(required=True)
    recipient.add_argument("--recipient-config")
    recipient.add_argument("--recipient-public-key")
    seal.add_argument("--recipient-sha256", required=True)
    seal.add_argument("--ttl-seconds", type=int, default=DEFAULT_TTL_SECONDS)

    receive = actions.add_parser("receive")
    receive.add_argument("--confirm", required=True)
    receive.add_argument("--input", required=True)
    receive.add_argument("--output", required=True)
    receive.add_argument("--expected-envelope-sha256", required=True)
    receive.add_argument("--expected-plaintext-sha256", required=True)
    receive.add_argument("--expected-plaintext-bytes", type=int, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        legacy = _legacy_transport()
        if args.action == "recipient-export":
            if args.confirm != "EXPORT-DESKTOP-MIGRATION-RECIPIENT":
                reject("fixed_confirmation_required")
            root = _migration_root(TARGET_HOST)
            output = _path_under_root(
                args.output, root, require_file=False, require_absent=True
            )
            _, config = legacy.receiver_identity()
            temporary, stream = _new_private_temp(output)
            try:
                with stream:
                    _write_exact(
                        stream, canonical(config), "recipient_config_write_failed"
                    )
                    stream.flush()
                    os.fsync(stream.fileno())
                _publish_no_replace(temporary, output, _windows_harden_file)
            finally:
                temporary.unlink(missing_ok=True)
            result = {
                "ok": True,
                "action": "recipient-export",
                "target_host": TARGET_HOST,
                "output": _relative_report_path(output, root),
                "recipient_sha256": config["recipient_sha256"],
                "private_key_exported": False,
            }
        elif args.action == "seal":
            if args.confirm != "SEAL-NOTERI-DESKTOP-BUNDLE":
                reject("fixed_confirmation_required")
            root = _migration_root(SOURCE_HOST)
            source = _path_under_root(args.input, root, require_file=True)
            output = _path_under_root(
                args.output, root, require_file=False, require_absent=True
            )
            recipient_path = args.recipient_config or args.recipient_public_key
            recipient_file = _path_under_root(recipient_path, root, require_file=True)
            recipient_key = _read_recipient_file(recipient_file, args.recipient_sha256)
            result = seal_file(
                source,
                output,
                recipient_key,
                ttl_seconds=args.ttl_seconds,
                harden_file=_windows_harden_file,
            )
            result.update(
                {
                    "action": "seal",
                    "input": _relative_report_path(source, root),
                    "output": _relative_report_path(output, root),
                    "plaintext_exported": False,
                    "private_key_exported": False,
                }
            )
        else:
            if args.confirm != "RECEIVE-NOTERI-DESKTOP-BUNDLE":
                reject("fixed_confirmation_required")
            root = _migration_root(TARGET_HOST)
            source = _path_under_root(args.input, root, require_file=True)
            output = _path_under_root(
                args.output, root, require_file=False, require_absent=True
            )
            private_key, _ = legacy.receiver_identity()
            result = receive_file(
                source,
                output,
                private_key,
                expected_envelope_sha256=args.expected_envelope_sha256,
                expected_plaintext_sha256=args.expected_plaintext_sha256,
                expected_plaintext_bytes=args.expected_plaintext_bytes,
                harden_file=_windows_harden_file,
            )
            result.update(
                {
                    "action": "receive",
                    "input": _relative_report_path(source, root),
                    "output": _relative_report_path(output, root),
                    "private_key_exported": False,
                }
            )
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except BundleTransportError as exc:
        print(json.dumps({"ok": False, "code": str(exc)}, separators=(",", ":")))
        return 1
    except Exception:  # noqa: BLE001 - the CLI boundary must never leak details
        print(json.dumps({"ok": False, "code": "transport_operation_failed"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
