#!/usr/bin/env python3
"""Restore the fixed CurrentUser-DPAPI DEV PostgreSQL archive into an empty owned candidate."""
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
import threading

HOST = "DESKTOP-PDQK954"
SOURCE_PROJECT = "wt-pc24x7-piloto"
PROJECT = "reqsys-dev-selfhosted"
INSTANCE = "pc24x7-selfhost-dev-v1"
HEADER = b"REQSYS-PG-DPAPI-V1\0"
MAX_ARCHIVE = 32 * 1024 * 1024
MAX_OUTPUT = 128 * 1024 * 1024
MAX_PROOF = 262144
SHA = re.compile(r"[0-9a-f]{40}")
DIGEST = re.compile(r"[0-9a-f]{64}")
NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,62}")
COPY = re.compile(r'COPY public\.(?:"([A-Za-z_][A-Za-z0-9_]*)"|([A-Za-z_][A-Za-z0-9_]*)) \(([^)]+)\) FROM stdin;')
SETVAL = re.compile(r"SELECT pg_catalog\.setval\('public\.([A-Za-z_][A-Za-z0-9_]*)', (-?[0-9]+), (true|false)\);")
CONTROL = re.compile(r"\\(?:un)?restrict [A-Za-z0-9]+")
CONFIRMATION = "RESTORE-PC24X7-CURRENT-PG-TO-EMPTY-DEV"
SESSION = "SET DateStyle = ISO; SET IntervalStyle = postgres; SET bytea_output = hex; SET extra_float_digits = 3; SET TIME ZONE 'UTC';"


class RestoreError(RuntimeError):
    def __init__(self, code: str, *, committed: bool = False):
        self.code = code if re.fullmatch(r"[a-z0-9_]+", code) else "restore_failed"
        self.committed = committed
        super().__init__(self.code)


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise RestoreError("duplicate_json_key")
        result[key] = value
    return result


def json_bytes(raw: bytes):
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=strict_object)
    except (UnicodeError, ValueError, TypeError):
        raise RestoreError("invalid_json") from None


def no_reparse_chain(path: Path) -> None:
    for current in (path, *path.parents):
        if not current.exists():
            raise RestoreError("required_private_path_missing")
        info = current.lstat()
        if current.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
            raise RestoreError("reparse_path_blocked")
        if current.is_file() and info.st_nlink != 1:
            raise RestoreError("hardlinked_file_blocked")


def check_backup_acl(path: Path, private) -> None:
    """Read-only acceptance of the producer's exact owner-only protected DACL."""
    no_reparse_chain(path)
    size = wintypes.DWORD()
    private.adv.GetFileSecurityW(str(path), 5, None, 0, ctypes.byref(size))
    if not size.value:
        raise RestoreError("backup_acl_read_failed")
    descriptor = ctypes.create_string_buffer(size.value)
    if not private.adv.GetFileSecurityW(
        str(path), 5, descriptor, size.value, ctypes.byref(size)
    ):
        raise RestoreError("backup_acl_read_failed")
    text = ctypes.c_void_p()
    if not private.adv.ConvertSecurityDescriptorToStringSecurityDescriptorW(
        descriptor, 1, 5, ctypes.byref(text), None
    ):
        raise RestoreError("backup_acl_read_failed")
    try:
        value = ctypes.wstring_at(text)
    finally:
        private.kernel.LocalFree(text)
    flags = r"(?:OICI)?" if path.is_dir() else ""
    match = re.fullmatch(
        r"O:([^:]+)D:P(?:AI)?((?:\(A;" + flags + r";FA;;;[^)]+\)){1,2})",
        value,
    )
    if not match:
        raise RestoreError("backup_acl_not_exclusive")
    owner = private._canonical_sid(match.group(1))
    identities = re.findall(r"\(A;" + flags + r";FA;;;([^)]+)\)", match.group(2))
    actual = sorted(private._canonical_sid(item) for item in identities)
    current = private._canonical_sid(private.sid)
    allowed = ([current], sorted((current, private._canonical_sid("SY"))))
    if owner != current or actual not in allowed:
        raise RestoreError("backup_acl_owner_mismatch")


def read_private(path: Path, private, limit: int, *, backup: bool = False) -> bytes:
    no_reparse_chain(path)
    if backup:
        check_backup_acl(path, private)
    else:
        private.check(path)
    if not path.is_file() or path.stat().st_size > limit:
        raise RestoreError("private_file_size_invalid")
    value = path.read_bytes()
    if len(value) > limit:
        raise RestoreError("private_file_size_invalid")
    return value


def digest_rows(rows: list[bytes]) -> str:
    digest = hashlib.sha256()
    for row in sorted(rows):
        digest.update(len(row).to_bytes(8, "big"))
        digest.update(row)
    return digest.hexdigest()


def identifiers(value: str) -> tuple[str, ...]:
    parts = []
    for raw in value.split(","):
        part = raw.strip()
        if part.startswith('"') and part.endswith('"'):
            part = part[1:-1]
        if not NAME.fullmatch(part):
            raise RestoreError("archive_column_not_supported")
        parts.append(part)
    if not parts or len(set(parts)) != len(parts):
        raise RestoreError("archive_columns_invalid")
    return tuple(parts)


def parse_archive_data(raw: bytes) -> tuple[dict, dict]:
    """Read COPY payloads; never execute statements extracted from this text."""
    if len(raw) > MAX_OUTPUT or b"\0" in raw:
        raise RestoreError("archive_data_size_invalid")
    tables = {}
    sequences = {}
    lines = raw.split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    position = 0
    while position < len(lines):
        try:
            line = lines[position].decode("utf-8")
        except UnicodeError:
            raise RestoreError("archive_text_not_utf8") from None
        position += 1
        match = COPY.fullmatch(line)
        if match:
            name = match.group(1) or match.group(2)
            if name in tables:
                raise RestoreError("duplicate_archive_table")
            columns = identifiers(match.group(3))
            rows = []
            while position < len(lines) and lines[position] != b"\\.":
                row = lines[position]
                # PostgreSQL text COPY represents embedded tabs/newlines as escapes.
                if len(row.split(b"\t")) != len(columns):
                    raise RestoreError("archive_copy_row_width_invalid")
                rows.append(row)
                position += 1
            if position == len(lines):
                raise RestoreError("archive_copy_terminator_missing")
            position += 1
            tables[name] = {
                "columns": columns, "count": len(rows),
                "digest": digest_rows(rows),
            }
            continue
        sequence = SETVAL.fullmatch(line)
        if sequence:
            name, value, called = sequence.groups()
            if name in sequences or not -(2 ** 63) <= int(value) < 2 ** 63:
                raise RestoreError("archive_sequence_invalid")
            sequences[name] = (str(int(value)), called == "true")
            continue
        if (not line or line.startswith("--")
                or re.fullmatch(r"SET [A-Za-z_]+ = [^;\r\n]+;", line)
                or line == "SELECT pg_catalog.set_config('search_path', '', false);"
                or CONTROL.fullmatch(line)):
            continue
        # No skipped INSERT/large object/materialized view/foreign namespace data.
        raise RestoreError("archive_data_statement_not_supported")
    if not tables or not sum(table["count"] for table in tables.values()):
        raise RestoreError("archive_has_no_rows")
    return tables, sequences


def parse_toc(raw: bytes) -> tuple[set[str], set[str], set[str]]:
    try:
        text = raw.decode("utf-8")
    except UnicodeError:
        raise RestoreError("archive_toc_not_utf8") from None
    tables, data, sequences = set(), set(), set()
    for line in text.splitlines():
        if not line or line.startswith(";"):
            continue
        entry = re.fullmatch(r"[0-9]+; [0-9]+ [0-9]+ (.+)", line)
        if not entry:
            raise RestoreError("archive_toc_entry_invalid")
        descriptor = entry.group(1)
        allowed = (
            "TABLE DATA", "SEQUENCE OWNED BY", "SEQUENCE SET", "DEFAULT",
            "FK CONSTRAINT", "CONSTRAINT", "INDEX", "TABLE", "SEQUENCE",
            "TYPE", "COMMENT", "ACL", "SCHEMA",
        )
        kind = next((value for value in allowed
                     if descriptor.startswith(value + " ")), None)
        if kind is None:
            raise RestoreError("archive_toc_kind_not_supported")
        remainder = descriptor[len(kind) + 1:]
        if kind == "SCHEMA":
            if not re.fullmatch(r"- public [A-Za-z_][A-Za-z0-9_]*", remainder):
                raise RestoreError("archive_namespace_not_supported")
        elif kind in {"COMMENT", "ACL"} and remainder.startswith("- SCHEMA public "):
            if not re.fullmatch(r"- SCHEMA public [A-Za-z_][A-Za-z0-9_]*", remainder):
                raise RestoreError("archive_namespace_not_supported")
        elif not remainder.startswith("public "):
            raise RestoreError("archive_namespace_not_supported")
        match = re.fullmatch(r"[0-9]+; [0-9]+ [0-9]+ (TABLE DATA|TABLE|SEQUENCE) public ([A-Za-z_][A-Za-z0-9_]*) [A-Za-z_][A-Za-z0-9_]*", line)
        if match:
            kind, name = match.groups()
            target = {"TABLE": tables, "TABLE DATA": data, "SEQUENCE": sequences}[kind]
            if name in target or not NAME.fullmatch(name):
                raise RestoreError("archive_toc_duplicate")
            target.add(name)
        elif re.search(r"; [0-9]+ [0-9]+ (?:TABLE DATA|TABLE(?! ATTACH)|SEQUENCE(?! OWNED BY| SET)|MATERIALIZED VIEW DATA|BLOB|BLOBS|LARGE OBJECT)\b", line):
            raise RestoreError("archive_relation_not_supported")
    if not tables or data != tables:
        raise RestoreError("archive_toc_data_incomplete")
    return tables, data, sequences


def restore_list(raw: bytes) -> bytes:
    """Keep every archive entry except the already-created default public schema."""
    lines = []
    for line in raw.decode("utf-8").splitlines():
        if re.fullmatch(r"[0-9]+; [0-9]+ [0-9]+ SCHEMA - public [A-Za-z_][A-Za-z0-9_]*", line):
            continue
        if re.fullmatch(r"[0-9]+; [0-9]+ [0-9]+ (?:COMMENT|ACL) - SCHEMA public [A-Za-z_][A-Za-z0-9_]*", line):
            continue
        if re.search(r"; [0-9]+ [0-9]+ SCHEMA ", line):
            raise RestoreError("archive_namespace_not_supported")
        lines.append(line)
    return ("\n".join(lines) + "\n").encode("utf-8")


def validate_backup(proof: dict, encrypted: bytes, archive: bytes) -> dict:
    required = {
        "schema_version": "1.0.0",
        "contract": "reqsys-current-dev-postgres-protected-backup",
        "status": "captured",
    }
    if not isinstance(proof, dict) or any(proof.get(k) != v for k, v in required.items()):
        raise RestoreError("backup_proof_contract_invalid")
    source = proof.get("source")
    info = proof.get("archive")
    protection = proof.get("protection")
    if not all(isinstance(item, dict) for item in (source, info, protection)):
        raise RestoreError("backup_proof_fields_invalid")
    exact = {"host": HOST, "project": SOURCE_PROJECT, "database": "reqsys", "role": "reqsys_app"}
    if any(source.get(k) != v for k, v in exact.items()):
        raise RestoreError("backup_source_identity_invalid")
    for name in ("api_container_id", "db_container_id"):
        if not DIGEST.fullmatch(str(source.get(name) or "")):
            raise RestoreError("backup_source_identity_invalid")
    if not SHA.fullmatch(str(source.get("build_sha") or "")):
        raise RestoreError("backup_build_sha_invalid")
    if not re.fullmatch(r"[0-9]{1,24}", str(source.get("system_identifier") or "")):
        raise RestoreError("backup_source_identity_invalid")
    if (info.get("format") != "postgresql_custom"
            or type(info.get("size_bytes")) is not int
            or info["size_bytes"] != len(archive)
            or not 0 < len(archive) <= MAX_ARCHIVE
            or not archive.startswith(b"PGDMP")
            or info.get("sha256") != hashlib.sha256(archive).hexdigest()):
        raise RestoreError("backup_archive_binding_invalid")
    if (protection.get("kind") != "windows-dpapi-current-user"
            or protection.get("entropy") != "none"
            or protection.get("encrypted_size_bytes") != len(encrypted)
            or protection.get("encrypted_sha256") != hashlib.sha256(encrypted).hexdigest()):
        raise RestoreError("backup_protection_binding_invalid")
    return source


def decrypt_current_user(encrypted: bytes) -> bytes:
    if os.name != "nt" or not encrypted.startswith(HEADER):
        raise RestoreError("windows_dpapi_archive_required")
    protected = encrypted[len(HEADER):]
    if not protected or len(protected) > MAX_ARCHIVE + 65536:
        raise RestoreError("encrypted_archive_size_invalid")

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

    buffer = (ctypes.c_ubyte * len(protected)).from_buffer_copy(protected)
    original = Blob(len(protected), buffer)
    clear = Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    crypt.CryptUnprotectData.argtypes = [
        ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.POINTER(Blob),
        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob),
    ]
    crypt.CryptUnprotectData.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    if not crypt.CryptUnprotectData(
        ctypes.byref(original), None, None, None, None, 1, ctypes.byref(clear)
    ):
        raise RestoreError("current_user_dpapi_decrypt_failed")
    try:
        if not 0 < clear.cbData <= MAX_ARCHIVE:
            raise RestoreError("decrypted_archive_size_invalid")
        return ctypes.string_at(clear.pbData, clear.cbData)
    finally:
        kernel.LocalFree(clear.pbData)


def bounded_run(args: list[str], payload: bytes, cwd: Path, limit: int,
                timeout: int) -> bytes:
    """Bound captured binary stdout while suppressing database stderr."""
    if len(payload) > MAX_OUTPUT or not 0 < limit <= MAX_OUTPUT:
        raise RestoreError("command_io_limit_invalid")
    try:
        process = subprocess.Popen(
            args, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, shell=False,
        )
    except OSError:
        raise RestoreError("database_command_unavailable") from None
    chunks = []
    failed = threading.Event()

    def read():
        total = 0
        try:
            while True:
                block = process.stdout.read(65536)
                if not block:
                    break
                total += len(block)
                if total > limit:
                    failed.set()
                    process.kill()
                    break
                chunks.append(block)
        except (OSError, ValueError):
            failed.set()

    def write():
        try:
            process.stdin.write(payload)
            process.stdin.close()
        except (OSError, ValueError):
            failed.set()

    reader = threading.Thread(target=read, daemon=True)
    writer = threading.Thread(target=write, daemon=True)
    reader.start()
    writer.start()
    try:
        result = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
        raise RestoreError("database_command_timeout") from None
    finally:
        writer.join(timeout=5)
        reader.join(timeout=5)
        process.stdout.close()
        process.stdin.close()
    if reader.is_alive() or writer.is_alive() or failed.is_set() or result:
        raise RestoreError("database_command_failed")
    return b"".join(chunks)


def load_publisher():
    path = Path(__file__).with_name("reqsys_self_hosted_dev_publish.py")
    spec = importlib.util.spec_from_file_location("reqsys_pg_publish", path)
    if spec is None or spec.loader is None:
        raise RestoreError("publisher_module_missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCHEMA_SQL = """
SELECT json_build_object(
 'tables', (SELECT COALESCE(json_agg(json_build_object(
   'name',c.relname,'owner',r.rolname,'kind',c.relkind,
   'columns',(SELECT COALESCE(json_agg(json_build_object(
      'name',a.attname,'generated',a.attgenerated,'type',format_type(a.atttypid,a.atttypmod),
      'not_null',a.attnotnull,'default',pg_get_expr(d.adbin,d.adrelid)
    ) ORDER BY a.attnum),'[]'::json) FROM pg_attribute a
      LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
      WHERE a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped),
   'constraints',(SELECT COALESCE(json_agg(json_build_object(
      'name',x.conname,'definition',pg_get_constraintdef(x.oid,true)
   ) ORDER BY x.conname),'[]'::json) FROM pg_constraint x WHERE x.conrelid=c.oid),
   'indexes',(SELECT COALESCE(json_agg(pg_get_indexdef(i.indexrelid) ORDER BY pg_get_indexdef(i.indexrelid)),'[]'::json)
      FROM pg_index i WHERE i.indrelid=c.oid)
 ) ORDER BY c.relname),'[]'::json)
 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 JOIN pg_roles r ON r.oid=c.relowner WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f')),
 'sequences', (SELECT COALESCE(json_agg(json_build_object(
    'name',c.relname,'owner',r.rolname,'start',s.seqstart::text,
    'increment',s.seqincrement::text,'min',s.seqmin::text,'max',s.seqmax::text,
    'cache',s.seqcache::text,'cycle',s.seqcycle
 ) ORDER BY c.relname),'[]'::json) FROM pg_sequence s JOIN pg_class c ON c.oid=s.seqrelid
 JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_roles r ON r.oid=c.relowner WHERE n.nspname='public'),
 'foreign_namespaces',(SELECT count(*) FROM pg_namespace WHERE nspname NOT IN ('public','information_schema')
    AND nspname NOT LIKE 'pg_%'),
 'other_objects',(SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public')
   +(SELECT count(*) FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace WHERE n.nspname='public'
       AND t.typtype IN ('d','e'))
);
"""


def canonical_digest(value) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")).hexdigest()


class Restorer:
    def __init__(self, publisher):
        self.publisher = publisher
        self.private = publisher.private
        self.root = publisher.root
        self.committed = False
        self.db = ""

    def binary(self, program: str, options: list[str], payload: bytes,
               limit: int = MAX_OUTPUT, timeout: int = 120) -> bytes:
        if program not in {"psql", "pg_restore"}:
            raise RestoreError("database_program_not_allowed")
        value = bounded_run(
            ["docker", "exec", "-i", self.db, program, *options],
            payload, self.publisher.source, limit, timeout,
        )
        self.publisher.events.append({"command": "postgres_" + program, "exit_code": 0})
        return value

    def sql(self, sql: str, limit: int = MAX_PROOF) -> bytes:
        return self.binary("psql", [
            "--no-psqlrc", "--quiet", "--tuples-only", "--no-align",
            "--set=ON_ERROR_STOP=1", "--username=reqsys_owner", "--dbname=reqsys",
        ], sql.encode("utf-8"), limit, 120)

    def schema(self) -> dict:
        value = json_bytes(self.sql("BEGIN READ ONLY;\n" + SCHEMA_SQL + "\nCOMMIT;\n"))
        if not isinstance(value, dict):
            raise RestoreError("target_schema_inventory_invalid")
        return value

    def owned_inactive(self) -> dict:
        self.publisher.validate_source()
        self.publisher.validate_engine()
        self.publisher.require_owned_project()
        ids = self.publisher.run("postgres_project_running", [
            "docker", "ps", "--filter", "label=com.docker.compose.project=" + PROJECT,
            "--format", "{{.ID}}",
        ]).splitlines()
        for container in ids:
            labels = json_bytes(self.publisher.run("postgres_running_labels", [
                "docker", "inspect", "--format", "{{json .Config.Labels}}", container
            ]).encode())
            if labels.get("com.docker.compose.service") not in {"db", "redis"}:
                raise RestoreError("candidate_application_already_running")
        identity = self.publisher.database_identity()
        self.db = identity["container_id"]
        version = self.sql("SHOW server_version_num;\n").decode().strip()
        if not version.isdigit() or not 160000 <= int(version) < 170000:
            raise RestoreError("postgresql_16_candidate_required")
        return identity

    def verify(self, tables: dict, sequences: dict, expected_schema: dict | None = None) -> dict:
        schema = self.schema()
        actual_tables = schema.get("tables")
        actual_sequences = schema.get("sequences")
        if (not isinstance(actual_tables, list) or not isinstance(actual_sequences, list)
                or schema.get("foreign_namespaces") != 0):
            raise RestoreError("restored_schema_invalid")
        if set(item.get("name") for item in actual_tables) != set(tables):
            raise RestoreError("restored_table_inventory_mismatch")
        if set(item.get("name") for item in actual_sequences) != set(sequences):
            raise RestoreError("restored_sequence_inventory_mismatch")
        for item in actual_tables:
            if item.get("owner") != "reqsys_app" or item.get("kind") != "r":
                raise RestoreError("restored_table_owner_or_kind_invalid")
            name = item["name"]
            columns = tuple(col.get("name") for col in item.get("columns", [])
                            if not col.get("generated"))
            if columns != tuple(tables[name]["columns"]):
                raise RestoreError("restored_column_inventory_mismatch")
            quoted = ",".join('"' + column + '"' for column in columns)
            raw = self.sql(
                "BEGIN READ ONLY;\n" + SESSION + '\nCOPY public."' + name
                + '" (' + quoted + ") TO STDOUT;\nCOMMIT;\n", MAX_OUTPUT,
            )
            if raw and not raw.endswith(b"\n"):
                raise RestoreError("target_copy_payload_incomplete")
            rows = raw.split(b"\n")[:-1] if raw else []
            expected = tables[name]
            if len(rows) != expected["count"] or digest_rows(rows) != expected["digest"]:
                raise RestoreError("archive_content_readback_mismatch", committed=self.committed)
        for item in actual_sequences:
            name = item["name"]
            if item.get("owner") != "reqsys_app":
                raise RestoreError("restored_sequence_owner_invalid")
            raw = self.sql(
                'BEGIN READ ONLY;\nSELECT json_build_array(last_value::text,is_called) FROM public."'
                + name + '";\nCOMMIT;\n'
            )
            observed = json_bytes(raw)
            if observed != list(sequences[name]):
                raise RestoreError("restored_sequence_value_mismatch", committed=self.committed)
        if expected_schema is not None and schema != expected_schema:
            raise RestoreError("restored_schema_changed")
        return schema

    def restore(self) -> dict:
        identity = self.owned_inactive()
        source_root = Path(os.environ["LOCALAPPDATA"]) / "ReqSys" / "SelfHostedDevMigration"
        encrypted_file = source_root / "current-dev-postgres.dump.dpapi"
        proof_file = source_root / "current-dev-postgres-proof.json"
        check_backup_acl(source_root, self.private)
        encrypted = read_private(encrypted_file, self.private, MAX_ARCHIVE + 65536, backup=True)
        backup = json_bytes(read_private(proof_file, self.private, MAX_PROOF, backup=True))
        archive = decrypt_current_user(encrypted)
        source = validate_backup(backup, encrypted, archive)
        if identity["container_id"] == source["db_container_id"]:
            raise RestoreError("source_target_container_collision")
        self.publisher.require_key_handoff(source["api_container_id"])
        toc = self.binary("pg_restore", ["--list"], archive, MAX_PROOF)
        toc_tables, toc_data, toc_sequences = parse_toc(toc)
        table_data = self.binary("pg_restore", [
            "--data-only", "--no-owner", "--no-privileges", "--file=-",
        ], archive)
        tables, sequences = parse_archive_data(table_data)
        if set(tables) != toc_data or set(sequences) != toc_sequences:
            raise RestoreError("archive_data_inventory_mismatch")
        if backup["archive"].get("toc_table_data_count") != len(tables):
            raise RestoreError("backup_toc_binding_invalid")
        target_proof = self.root / "restore-proof.json"
        if target_proof.exists():
            raise RestoreError("existing_restore_proof_preserved")
        empty = self.schema()
        if (empty.get("tables") or empty.get("sequences")
                or empty.get("foreign_namespaces") != 0 or empty.get("other_objects") != 0):
            raise RestoreError("restore_target_schema_not_empty")
        # The init script created public already. The temporary TOC contains only
        # metadata and excludes only that default schema and its comment/ACL.
        manifest = restore_list(toc)
        nonce = secrets.token_hex(16)
        manifest_path = "/tmp/reqsys-dev-pg-restore-" + nonce + ".list"
        try:
            written = bounded_run(
                ["docker", "exec", "-i", self.db, "tee", manifest_path],
                manifest, self.publisher.source, MAX_PROOF, 20,
            )
            if written != manifest:
                raise RestoreError("restore_manifest_write_mismatch")
            # Every remaining schema/data/sequence entry is restored atomically.
            self.binary("pg_restore", [
                "--exit-on-error", "--single-transaction", "--no-owner",
                "--no-privileges", "--role=reqsys_app", "--username=reqsys_owner",
                "--dbname=reqsys", "--use-list=" + manifest_path,
            ], archive, MAX_PROOF, 180)
            self.committed = True
        finally:
            if self.publisher.database_identity() != identity:
                raise RestoreError("manifest_cleanup_target_identity_changed",
                                   committed=self.committed)
            bounded_run(
                ["docker", "exec", self.db, "rm", "--", manifest_path],
                b"", self.publisher.source, 4096, 20,
            )
        schema = self.verify(tables, sequences)
        if self.publisher.database_identity() != identity:
            raise RestoreError("target_identity_changed", committed=True)
        if read_private(encrypted_file, self.private, MAX_ARCHIVE + 65536, backup=True) != encrypted:
            raise RestoreError("protected_archive_changed", committed=True)
        self.publisher.require_key_handoff(source["api_container_id"])
        rows = sum(item["count"] for item in tables.values())
        result = {
            "schema_version": "1",
            "contract": "reqsys-current-postgres-restore",
            "source_engine": "postgresql",
            "status": "verified",
            "host": HOST,
            "project": PROJECT,
            "instance": INSTANCE,
            "target_sha": self.publisher.expected,
            "source_sha256": backup["archive"]["sha256"],
            "source_project": SOURCE_PROJECT,
            "backup_source_identity": {
                "api_container_id": source["api_container_id"],
                "database_container_id": source["db_container_id"],
                "postgres_system_identifier": source["system_identifier"],
                "database": "reqsys", "role": "reqsys_app",
            },
            "database_identity": identity,
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "source_rows": rows,
            "copied_rows": rows,
            "table_counts": {name: item["count"] for name, item in tables.items()},
            "archive_validated": True,
            "content_digests_match": True,
            "independent_readback": True,
            "migration_committed": True,
            "sequences_verified": True,
            "schema_inventory_verified": True,
            "runtime_keys_preserved": True,
            "private_archive_content": tables,
            "private_archive_sequences": sequences,
            "private_restored_schema": schema,
            "source_writes_frozen": False,
            "current_source_freshness_verified": False,
            "authenticated_flow_verified": False,
            "public_ingress_verified": False,
            "usable": False,
        }
        result["proof_integrity_sha256"] = self.publisher.proof_integrity(result) if hasattr(self.publisher, "proof_integrity") else canonical_digest(result)
        self.private.preserving(
            target_proof, (json.dumps(result, sort_keys=True, indent=2) + "\n").encode(),
        )
        return result


def validate_restore_proof(proof: dict, expected_sha: str, identity: dict,
                           backup_sha: str, now: datetime) -> dict:
    exact = {
        "schema_version": "1", "contract": "reqsys-current-postgres-restore",
        "source_engine": "postgresql", "status": "verified", "host": HOST,
        "project": PROJECT, "instance": INSTANCE, "target_sha": expected_sha,
        "source_sha256": backup_sha, "source_project": SOURCE_PROJECT,
        "database_identity": identity, "archive_validated": True,
        "content_digests_match": True, "independent_readback": True,
        "migration_committed": True, "sequences_verified": True,
        "schema_inventory_verified": True, "runtime_keys_preserved": True,
    }
    if not isinstance(proof, dict) or any(proof.get(k) != v for k, v in exact.items()):
        raise RestoreError("restore_proof_binding_invalid")
    unsigned = {key: value for key, value in proof.items() if key != "proof_integrity_sha256"}
    if proof.get("proof_integrity_sha256") != canonical_digest(unsigned):
        raise RestoreError("restore_proof_integrity_invalid")
    try:
        verified = datetime.fromisoformat(proof["verified_at"].replace("Z", "+00:00"))
        age = (now - verified).total_seconds()
    except (KeyError, TypeError, ValueError):
        raise RestoreError("restore_proof_time_invalid") from None
    if not 0 <= age <= 3600:
        raise RestoreError("restore_proof_stale")
    counts = proof.get("table_counts")
    tables = proof.get("private_archive_content")
    sequences = proof.get("private_archive_sequences")
    schema = proof.get("private_restored_schema")
    if not all(isinstance(value, dict) for value in (counts, tables, sequences, schema)):
        raise RestoreError("restore_proof_private_inventory_invalid")
    if (not counts or set(counts) != set(tables)
            or any(not NAME.fullmatch(name) or type(count) is not int or count < 0
                   for name, count in counts.items())
            or sum(counts.values()) <= 0
            or proof.get("source_rows") != sum(counts.values())
            or proof.get("copied_rows") != sum(counts.values())):
        raise RestoreError("restore_proof_counts_invalid")
    for name, table in tables.items():
        if (not isinstance(table, dict) or table.get("count") != counts[name]
                or not DIGEST.fullmatch(str(table.get("digest") or ""))
                or not isinstance(table.get("columns"), list)
                or not table["columns"]
                or len(set(table["columns"])) != len(table["columns"])
                or any(not isinstance(column, str) or not NAME.fullmatch(column)
                       for column in table["columns"])):
            raise RestoreError("restore_proof_copy_inventory_invalid")
    for name, sequence in sequences.items():
        if (not NAME.fullmatch(name) or not isinstance(sequence, list)
                or len(sequence) != 2
                or not isinstance(sequence[0], str)
                or not re.fullmatch(r"-?[0-9]+", sequence[0])
                or type(sequence[1]) is not bool):
            raise RestoreError("restore_proof_sequence_invalid")
    source = proof.get("backup_source_identity")
    if (not isinstance(source, dict)
            or not DIGEST.fullmatch(str(source.get("api_container_id") or ""))):
        raise RestoreError("restore_proof_source_identity_invalid")
    return proof


def verify_existing(publisher, backup_sha: str) -> dict:
    """For activation: independent archive-content readback before starting the API."""
    restorer = Restorer(publisher)
    identity = publisher.database_identity()
    restorer.db = identity["container_id"]
    proof = json_bytes(read_private(
        publisher.root / "restore-proof.json", publisher.private, MAX_OUTPUT
    ))
    validate_restore_proof(
        proof, publisher.expected, identity, backup_sha, datetime.now(timezone.utc),
    )
    publisher.require_key_handoff(proof["backup_source_identity"]["api_container_id"])
    restorer.committed = True
    restorer.verify(
        proof["private_archive_content"], proof["private_archive_sequences"],
        proof["private_restored_schema"],
    )
    return proof


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--confirm", required=True, choices=(CONFIRMATION,))
    args = parser.parse_args(argv)
    report = {
        "schema_version": "1", "contract": "reqsys-current-postgres-restore",
        "host": HOST, "project": PROJECT, "status": "blocked",
        "migration_committed": False, "restore_verified": False,
        "public_pointer_changed": False, "source_modified": False,
        "production_touched": False, "secret_values_exposed": False,
        "usable": False,
    }
    restorer = None
    try:
        if os.name != "nt" or socket.gethostname().casefold() != HOST.casefold():
            raise RestoreError("fixed_windows_host_required")
        if (not SHA.fullmatch(args.expected_sha)
                or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,120}", args.correlation_id)):
            raise RestoreError("invocation_binding_invalid")
        publish = load_publisher()
        publisher = publish.Publisher(
            args.source_root, args.expected_sha,
            publish.WindowsPrivateFiles(), args.correlation_id,
        )
        restorer = Restorer(publisher)
        proof = restorer.restore()
        report.update({
            "status": "database_restored", "migration_committed": True,
            "restore_verified": True, "restored_rows": proof["copied_rows"],
            "tables_verified": len(proof["table_counts"]),
            "sequences_verified": True, "archive_content_compared": True,
            "runtime_keys_preserved": True,
            "current_source_freshness_verified": False,
        })
        code = 0
    except Exception as error:
        report["error"] = error.code if isinstance(error, RestoreError) else "restore_operation_failed"
        report["migration_committed"] = bool(restorer and restorer.committed)
        code = 2
    print(json.dumps(report, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
