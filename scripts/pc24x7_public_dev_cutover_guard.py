#!/usr/bin/env python3
"""Prepara e valida backup/rollback para o cutover público DEV do PC24x7.

O manifesto e o backup cifrado permanecem privados no host. A saída pública
contém somente flags, fingerprints e códigos allowlisted.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path
from typing import Any, Callable

try:
    from scripts import dev_runtime_recovery as recovery
except (ImportError, ModuleNotFoundError):
    import importlib.util

    _source = Path(__file__).resolve().with_name("dev_runtime_recovery.py")
    _spec = importlib.util.spec_from_file_location("reqsys_dev_runtime_recovery", _source)
    if _spec is None or _spec.loader is None:
        raise RuntimeError("recovery_helper_unavailable")
    recovery = importlib.util.module_from_spec(_spec)
    sys.modules[_spec.name] = recovery
    _spec.loader.exec_module(recovery)


HOST = recovery.HOST
PROJECT = recovery.PROJECT
ROOT = recovery.ROOT
ENVIRONMENT = "dev"
DB_SERVICE = "db"
PREPARE_CONFIRM = "PREPARE-PC24X7-PUBLIC-DEV-CUTOVER"
ROLLBACK_CONFIRM = "ROLLBACK-PC24X7-PUBLIC-DEV-CUTOVER"
PUBLIC_RECEIPT_KEYS = {
    "status",
    "reason_code",
    "fingerprint",
    "backup_verified",
    "isolated_restore_verified",
    "rollback_images_prepared",
    "rollback_ok",
    "database_unchanged",
    "production_touched",
}
MAX_DUMP_BYTES = 512 * 1024 * 1024
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
CORRELATION = re.compile(r"[a-z0-9][a-z0-9-]{7,139}\Z")


class CutoverBlocked(RuntimeError):
    """Erro sanitizado; nunca inclui stderr, paths privados ou valores do banco."""


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def dpapi(value: bytes, *, encrypt: bool) -> bytes:
    if os.name != "nt" or not value or len(value) > MAX_DUMP_BYTES + 65536:
        raise CutoverBlocked("dpapi_unavailable_or_oversized")
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    buffer = ctypes.create_string_buffer(value)
    source = _Blob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = _Blob()
    proc = crypt.CryptProtectData if encrypt else crypt.CryptUnprotectData
    proc.argtypes = [ctypes.POINTER(_Blob), ctypes.c_void_p, ctypes.c_void_p,
                     ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
                     ctypes.POINTER(_Blob)]
    proc.restype = wintypes.BOOL
    if not proc(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise CutoverBlocked("dpapi_operation_failed")
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    try:
        protected = ctypes.string_at(output.pbData, output.cbData)
    finally:
        kernel.LocalFree(ctypes.cast(output.pbData, ctypes.c_void_p))
    if not protected:
        raise CutoverBlocked("dpapi_empty_output")
    return protected


def _docker(argv: list[str], *, data: bytes | None = None, timeout: int = 120,
            can_fail: bool = False) -> bytes:
    try:
        result = subprocess.run(["docker", *argv], input=data, capture_output=True,
                                check=False, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        raise CutoverBlocked("docker_unavailable") from None
    if result.returncode != 0 and not can_fail:
        raise CutoverBlocked("docker_command_failed")
    if len(result.stdout) > MAX_DUMP_BYTES + 65536:
        raise CutoverBlocked("docker_output_oversized")
    return result.stdout


def _text(argv: list[str], *, timeout: int = 120) -> str:
    try:
        return _docker(argv, timeout=timeout).decode("utf-8", errors="strict").strip()
    except UnicodeError:
        raise CutoverBlocked("docker_text_invalid") from None


def _unique_container(service: str) -> str:
    raw = _text([
        "ps", "--filter", f"label=com.docker.compose.project={PROJECT}",
        "--filter", f"label=com.docker.compose.service={service}", "--format", "{{.ID}}",
    ])
    ids = [item.strip() for item in raw.splitlines() if item.strip()]
    if len(ids) != 1:
        raise CutoverBlocked(f"container_cardinality_{service}")
    return ids[0]


def _db_identity(container: str, root: Path) -> str:
    try:
        payload = json.loads(_text(["inspect", container]))
        item = payload[0]
        labels = (item.get("Config") or {}).get("Labels") or {}
        image = recovery.image_id(item.get("Image"))
    except (ValueError, KeyError, IndexError, TypeError, recovery.RecoveryError):
        raise CutoverBlocked("database_identity_invalid") from None
    if (labels.get("com.docker.compose.project") != PROJECT or
            labels.get("com.docker.compose.service") != DB_SERVICE):
        raise CutoverBlocked("database_identity_mismatch")
    try:
        observed_root = Path(labels.get("com.docker.compose.project.working_dir", "")).resolve(strict=True)
        expected_root = root.resolve(strict=True)
    except OSError:
        raise CutoverBlocked("database_working_dir_invalid") from None
    if observed_root != expected_root:
        raise CutoverBlocked("database_working_dir_mismatch")
    return image


_SOURCE_PREFIX = [
    "sh", "-ec",
    'exec psql --no-psqlrc --tuples-only --no-align --set ON_ERROR_STOP=1 '
    '--username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --command "$1"',
    "reqsys-psql",
]


def _psql(container: str, sql: str, *, isolated: bool = False) -> str:
    if isolated:
        argv = ["exec", container, "psql", "--no-psqlrc", "--tuples-only", "--no-align",
                "--set", "ON_ERROR_STOP=1", "--username=postgres",
                "--dbname=reqsys_restore", "--command", sql]
    else:
        argv = ["exec", container, *_SOURCE_PREFIX, sql]
    return _text(argv, timeout=90)


def _quote_identifier(value: str) -> str:
    if not value or any(ord(char) < 32 for char in value):
        raise CutoverBlocked("database_identifier_invalid")
    return '"' + value.replace('"', '""') + '"'


def database_snapshot(container: str, *, isolated: bool = False) -> dict[str, Any]:
    table_payload = _psql(
        container,
        "SELECT COALESCE(json_agg(json_build_array(table_schema,table_name) "
        "ORDER BY table_schema,table_name),'[]'::json) FROM information_schema.tables "
        "WHERE table_type='BASE TABLE' AND table_schema NOT IN ('pg_catalog','information_schema');",
        isolated=isolated,
    )
    try:
        tables = json.loads(table_payload)
    except ValueError:
        raise CutoverBlocked("database_table_inventory_invalid") from None
    if not isinstance(tables, list) or not tables:
        raise CutoverBlocked("database_table_inventory_empty")
    counts: list[list[Any]] = []
    for item in tables:
        if not isinstance(item, list) or len(item) != 2 or not all(isinstance(v, str) for v in item):
            raise CutoverBlocked("database_table_inventory_invalid")
        qualified = f"{_quote_identifier(item[0])}.{_quote_identifier(item[1])}"
        raw = _psql(container, f"SELECT count(*) FROM {qualified};", isolated=isolated)
        try:
            count = int(raw)
        except ValueError:
            raise CutoverBlocked("database_row_count_invalid") from None
        counts.append([item[0], item[1], count])
    schema = _psql(
        container,
        "SELECT COALESCE(json_agg(json_build_array(table_schema,table_name,column_name,"
        "ordinal_position,data_type,is_nullable,column_default) ORDER BY table_schema,table_name,"
        "ordinal_position),'[]'::json) FROM information_schema.columns WHERE table_schema NOT IN "
        "('pg_catalog','information_schema');",
        isolated=isolated,
    )
    sequences = _psql(
        container,
        "SELECT COALESCE(json_agg(json_build_array(schemaname,sequencename,last_value) "
        "ORDER BY schemaname,sequencename),'[]'::json) FROM pg_sequences WHERE schemaname "
        "NOT IN ('pg_catalog','information_schema');",
        isolated=isolated,
    )
    material = {"tables": tables, "counts": counts, "schema": schema, "sequences": sequences}
    return {
        "table_count": len(tables),
        "row_count_total": sum(item[2] for item in counts),
        "fingerprint": hashlib.sha256(
            json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest(),
    }


def _dump_database(container: str) -> bytes:
    size_raw = _psql(container, "SELECT pg_database_size(current_database());")
    try:
        size = int(size_raw)
    except ValueError:
        raise CutoverBlocked("database_size_invalid") from None
    if size < 1 or size > MAX_DUMP_BYTES:
        raise CutoverBlocked("database_size_out_of_policy")
    dump = _docker([
        "exec", container, "sh", "-ec",
        'exec pg_dump --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" '
        '--format=custom --no-owner --no-privileges',
    ], timeout=600)
    if not dump or len(dump) > MAX_DUMP_BYTES:
        raise CutoverBlocked("database_dump_invalid")
    return dump


def _isolated_restore(dump: bytes, image: str, correlation_id: str,
                      expected: dict[str, Any], sleeper: Callable[[float], None] = time.sleep) -> None:
    suffix = hashlib.sha256(correlation_id.encode()).hexdigest()[:16]
    container = f"reqsys-public-dev-restore-{suffix}"
    volume = f"reqsys-public-dev-restore-{suffix}"
    if _text(["volume", "ls", "--filter", f"name=^{volume}$", "--format", "{{.Name}}"]).strip():
        raise CutoverBlocked("isolated_restore_volume_collision")
    _docker(["volume", "create", "--label", "reqsys.scope=public-dev-restore", volume])
    volume_created = True
    created = False
    try:
        _docker([
            "create", "--name", container, "--network", "none",
            "--label", "reqsys.scope=public-dev-restore",
            "--env", "POSTGRES_HOST_AUTH_METHOD=trust", "--env", "POSTGRES_DB=reqsys_restore",
            "--volume", f"{volume}:/var/lib/postgresql/data", image,
        ])
        created = True
        _docker(["start", container])
        ready = False
        for _ in range(60):
            raw = _docker(["exec", container, "pg_isready", "-U", "postgres", "-d", "reqsys_restore"],
                          can_fail=True, timeout=10)
            if b"accepting connections" in raw:
                ready = True
                break
            sleeper(1)
        if not ready:
            raise CutoverBlocked("isolated_restore_not_ready")
        _docker([
            "exec", "-i", container, "pg_restore", "--username=postgres",
            "--dbname=reqsys_restore", "--no-owner", "--no-privileges", "--exit-on-error",
        ], data=dump, timeout=900)
        restored = database_snapshot(container, isolated=True)
        if restored != expected:
            raise CutoverBlocked("isolated_restore_mismatch")
    finally:
        if created:
            _docker(["rm", "-f", container], can_fail=True)
        if volume_created:
            _docker(["volume", "rm", "-f", volume], can_fail=True)


def _private_path(root: Path, correlation_id: str, suffix: str) -> Path:
    if not CORRELATION.fullmatch(correlation_id):
        raise CutoverBlocked("correlation_id_invalid")
    directory = root / ".reqsys-recovery"
    if directory.exists() and (directory.is_symlink() or not directory.is_dir()):
        raise CutoverBlocked("recovery_directory_invalid")
    directory.mkdir(mode=0o700, exist_ok=True)
    return directory / f"public-dev-{correlation_id}.{suffix}"


def _exclusive_write(path: Path, value: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError:
        raise CutoverBlocked("private_backup_write_failed") from None


def _outer_fingerprint(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _seal(value: dict[str, Any]) -> dict[str, Any]:
    result = dict(value)
    result["fingerprint"] = _outer_fingerprint(result)
    return result


def prepare(expected_sha: str, correlation_id: str, manifest_path: Path, *, root: Path = ROOT,
            runner: Any | None = None, hostname: str | None = None,
            protect: Callable[..., bytes] = dpapi,
            restore: Callable[..., None] = _isolated_restore) -> dict[str, Any]:
    expected_sha = expected_sha.lower()
    if not SHA40.fullmatch(expected_sha):
        raise CutoverBlocked("expected_sha_invalid")
    recovery.observed_scope(hostname or socket.gethostname())
    runner = runner or recovery.SubprocessRunner()
    captured = recovery.capture(runner, root=root, hostname=HOST)
    prepared = recovery.prepare(captured, runner, captured["fingerprint"], root)
    db = _unique_container(DB_SERVICE)
    db_image = _db_identity(db, root)
    baseline = database_snapshot(db)
    dump = _dump_database(db)
    restore(dump, db_image, correlation_id, baseline)
    protected = protect(dump, encrypt=True)
    backup_path = _private_path(root, correlation_id, "pgdump.dpapi")
    _exclusive_write(backup_path, protected)
    body = {
        "schema": 1,
        "state": "prepared",
        "host": HOST,
        "environment": ENVIRONMENT,
        "project": PROJECT,
        "expected_sha": expected_sha,
        "correlation_id": correlation_id,
        "runtime_recovery": prepared,
        "database": {
            "image_id": db_image,
            "backup": recovery.file_meta(backup_path, root),
            "plain_sha256": hashlib.sha256(dump).hexdigest(),
            "baseline": baseline,
            "dpapi_user_scope": True,
            "isolated_restore_verified": True,
        },
        "production_touched": False,
    }
    manifest = _seal(body)
    if manifest_path.exists():
        raise CutoverBlocked("manifest_collision")
    if manifest_path.parent.resolve() != (root / ".reqsys-recovery").resolve():
        raise CutoverBlocked("manifest_path_refused")
    _exclusive_write(manifest_path, json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode())
    return manifest


def validate(manifest: dict[str, Any], expected_fingerprint: str, expected_sha: str,
             *, root: Path = ROOT, runner: Any | None = None,
             unprotect: Callable[..., bytes] = dpapi) -> None:
    if manifest.get("fingerprint") != expected_fingerprint:
        raise CutoverBlocked("external_fingerprint_mismatch")
    unsigned = {key: value for key, value in manifest.items() if key != "fingerprint"}
    if _outer_fingerprint(unsigned) != expected_fingerprint:
        raise CutoverBlocked("manifest_integrity_failed")
    if (manifest.get("host") != HOST or manifest.get("environment") != ENVIRONMENT or
            manifest.get("project") != PROJECT or manifest.get("expected_sha") != expected_sha.lower() or
            manifest.get("state") != "prepared" or manifest.get("production_touched") is not False):
        raise CutoverBlocked("manifest_scope_invalid")
    runner = runner or recovery.SubprocessRunner()
    nested = manifest.get("runtime_recovery")
    if not isinstance(nested, dict):
        raise CutoverBlocked("runtime_recovery_missing")
    recovery.validate(nested, runner, nested.get("fingerprint"), root, True)
    database = manifest.get("database")
    if not isinstance(database, dict) or database.get("isolated_restore_verified") is not True:
        raise CutoverBlocked("database_evidence_invalid")
    record = database.get("backup")
    if not isinstance(record, dict):
        raise CutoverBlocked("database_backup_missing")
    path = root / str(record.get("relative_path", ""))
    if recovery.file_meta(path, root) != record:
        raise CutoverBlocked("database_backup_changed")
    try:
        plain = unprotect(path.read_bytes(), encrypt=False)
    except OSError:
        raise CutoverBlocked("database_backup_unreadable") from None
    if hashlib.sha256(plain).hexdigest() != database.get("plain_sha256"):
        raise CutoverBlocked("database_backup_plain_hash_mismatch")


def rollback(manifest: dict[str, Any], expected_fingerprint: str, expected_sha: str,
             *, root: Path = ROOT, runner: Any | None = None) -> dict[str, Any]:
    runner = runner or recovery.SubprocessRunner()
    validate(manifest, expected_fingerprint, expected_sha, root=root, runner=runner)
    nested = manifest["runtime_recovery"]
    result = recovery.rollback(
        nested,
        runner,
        nested["fingerprint"],
        root=root,
        hostname=HOST,
        allow_unhealthy_current=True,
    )
    db = _unique_container(DB_SERVICE)
    observed = database_snapshot(db)
    if observed != manifest["database"]["baseline"]:
        raise CutoverBlocked("database_changed_after_runtime_rollback")
    return {"rollback_ok": result.get("rollback_ok") is True, "database_unchanged": True,
            "production_touched": False}


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise CutoverBlocked("manifest_unreadable") from None
    if not isinstance(value, dict):
        raise CutoverBlocked("manifest_invalid")
    return value


def write_public_receipt(path: Path, value: dict[str, Any], *, root: Path = ROOT) -> None:
    receipt_parent = root / "artifacts" / "pc24x7-public-dev"
    if receipt_parent.exists() and (receipt_parent.is_symlink() or not receipt_parent.is_dir()):
        raise CutoverBlocked("public_receipt_directory_invalid")
    receipt_parent.mkdir(parents=True, exist_ok=True)
    allowed_parent = receipt_parent.resolve()
    resolved = path.resolve()
    if resolved.parent != allowed_parent or not re.fullmatch(r"cutover-[a-z0-9._-]+\.json", resolved.name):
        raise CutoverBlocked("public_receipt_path_refused")
    if set(value) - PUBLIC_RECEIPT_KEYS:
        raise CutoverBlocked("public_receipt_contains_private_fields")
    _exclusive_write(
        resolved,
        (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode(),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "validate", "rollback"))
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--expected-fingerprint")
    parser.add_argument("--receipt-file", type=Path)
    parser.add_argument("--confirm")
    args = parser.parse_args()
    try:
        if args.mode == "prepare":
            if args.confirm != PREPARE_CONFIRM:
                raise CutoverBlocked("confirmation_refused")
            value = prepare(args.expected_sha, args.correlation_id, args.manifest)
            result = {"status": "prepared", "fingerprint": value["fingerprint"],
                      "backup_verified": True, "isolated_restore_verified": True,
                      "rollback_images_prepared": True, "production_touched": False}
        elif args.mode == "validate":
            validate(load(args.manifest), str(args.expected_fingerprint or ""), args.expected_sha)
            result = {"status": "validated", "backup_verified": True,
                      "isolated_restore_verified": True, "rollback_images_prepared": True,
                      "production_touched": False}
        else:
            if args.confirm != ROLLBACK_CONFIRM:
                raise CutoverBlocked("confirmation_refused")
            result = rollback(load(args.manifest), str(args.expected_fingerprint or ""), args.expected_sha)
        if args.receipt_file is not None:
            write_public_receipt(args.receipt_file, result)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except (CutoverBlocked, recovery.RecoveryError) as exc:
        print(json.dumps({"status": "blocked", "reason_code": str(exc).split(":", 1)[0],
                          "production_touched": False}, sort_keys=True, separators=(",", ":")))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
