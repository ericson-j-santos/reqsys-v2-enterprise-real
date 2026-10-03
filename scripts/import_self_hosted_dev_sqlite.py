#!/usr/bin/env python3
"""Importa somente um snapshot SQLite validado para PostgreSQL isolado e vazio.

Executado em container one-off, antes de iniciar a API. Nenhum segredo e dado
de linha aparece em argumentos, logs ou evidencia. O wrapper do host associa
a evidencia a host/projeto/container/system_identifier antes de ativar DEV.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import re
import sys
import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import (
    JSON, Boolean, Date, DateTime, Enum, Float, Integer, LargeBinary,
    MetaData, Numeric, String, Text, Time, Uuid, cast, create_engine,
    func, inspect, select, text, type_coerce,
)

from sqlalchemy.types import NullType

SOURCE = Path("/migration/source.db")
EVIDENCE = Path("/migration-evidence/sqlite-postgres-import.json")


class ImportFailure(RuntimeError):
    def __init__(self, code: str, *, committed: bool = False, details: dict | None = None):
        super().__init__(code)
        self.code = code
        self.committed = committed
        self.details = details or {}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            digest.update(block)
    return digest.hexdigest()


def quote_table(connection, table) -> str:
    quote = connection.dialect.identifier_preparer.quote
    return ".".join(quote(part) for part in (table.schema, table.name) if part)


def column_kind(column) -> str:
    value = column.type
    for cls, name in (
        (JSON, "json"), (Boolean, "boolean"), (Enum, "enum"),
        (DateTime, "datetime"), (Date, "date"), (Time, "time"),
        (Integer, "integer"), (Float, "float"), (Numeric, "decimal"),
        (LargeBinary, "binary"), (Uuid, "uuid"), (String, "string"),
    ):
        if isinstance(value, cls):
            return name
    raise ImportFailure("unsupported_target_column_type")


def _json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ImportFailure("duplicate_json_object_key")
        result[key] = value
    return result


def _json_numbers(value):
    if isinstance(value, Decimal):
        candidate = float(value)
        if not value.is_finite() or not math.isfinite(candidate) or Decimal(str(candidate)) != value:
            raise ImportFailure("json_numeric_precision_loss")
        return candidate
    if isinstance(value, list):
        return [_json_numbers(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_numbers(item) for key, item in value.items()}
    return value


def convert_value(value, column):
    if value is None:
        if not column.nullable:
            raise ImportFailure("null_for_required_column")
        return None
    kind = column_kind(column)
    if kind == "json":
        # JSON columns are selected as SQL text, distinguishing SQL NULL
        # from JSON null and avoiding different driver representations.
        if not isinstance(value, str):
            raise ImportFailure("json_not_text")
        try:
            parsed = _json_numbers(json.loads(value, parse_float=Decimal, parse_constant=Decimal, object_pairs_hook=_json_object))
        except (TypeError, ValueError):
            raise ImportFailure("invalid_json") from None
        return JSON.NULL if parsed is None else parsed
    if kind == "boolean":
        if type(value) not in (int, bool) or value not in (0, 1):
            raise ImportFailure("invalid_boolean")
        return bool(value)
    if kind == "integer":
        if type(value) is not int:
            raise ImportFailure("invalid_integer")
        return value
    if kind == "decimal":
        if not isinstance(value, (int, float, Decimal)) or isinstance(value, bool):
            raise ImportFailure("invalid_decimal")
        result = Decimal(str(value))
        if not result.is_finite():
            raise ImportFailure("nonfinite_number")
        return result
    if kind == "float":
        if not isinstance(value, (int, float, Decimal)) or isinstance(value, bool):
            raise ImportFailure("invalid_float")
        result = float(value)
        if not math.isfinite(result):
            raise ImportFailure("nonfinite_number")
        if isinstance(value, (int, Decimal)) and Decimal(str(result)) != Decimal(value):
            raise ImportFailure("float_precision_loss")
        return result
    if kind in ("datetime", "date", "time"):
        expected = {"datetime": datetime, "date": date, "time": time}[kind]
        if isinstance(value, str):
            try:
                value = expected.fromisoformat(value)
            except ValueError:
                raise ImportFailure("invalid_temporal_value") from None
        if not isinstance(value, expected) or (kind == "date" and isinstance(value, datetime)):
            raise ImportFailure("invalid_temporal_value")
        if kind in ("datetime", "time"):
            aware = value.utcoffset() is not None
            if bool(column.type.timezone) != aware:
                raise ImportFailure("temporal_timezone_mismatch")
        return value
    if kind == "uuid":
        try:
            return uuid.UUID(str(value))
        except ValueError:
            raise ImportFailure("invalid_uuid") from None
    if kind == "binary":
        if not isinstance(value, (bytes, bytearray, memoryview)):
            raise ImportFailure("invalid_binary")
        return bytes(value)
    if not isinstance(value, str):
        raise ImportFailure("invalid_string")
    if kind == "enum" and value not in column.type.enums:
        raise ImportFailure("invalid_enum")
    if column.type.length is not None and len(value) > column.type.length:
        raise ImportFailure("string_too_long")
    return value


def canonical(value):
    # Every representation is typed recursively. User JSON objects cannot
    # imitate SQL NULL, JSON null, Decimal or another tagged scalar.
    if value is JSON.NULL:
        return ["json_null"]
    if value is None:
        return ["sql_null"]
    if isinstance(value, bool):
        return ["boolean", value]
    if isinstance(value, int):
        return ["integer", str(value)]
    if isinstance(value, Decimal):
        sign, digits, exponent = value.as_tuple()
        if not any(digits):
            return ["decimal", 0, "0", 0]
        digits = list(digits)
        while digits[-1] == 0:
            digits.pop()
            exponent += 1
        # Decimal.normalize() can round at the current context precision.
        return ["decimal", sign, "".join(str(digit) for digit in digits), exponent]
    if isinstance(value, datetime):
        if value.utcoffset() is not None:
            value = value.astimezone(timezone.utc)
        return ["datetime", value.isoformat(timespec="microseconds")]
    if isinstance(value, (date, time)):
        return [type(value).__name__, value.isoformat()]
    if isinstance(value, uuid.UUID):
        return ["uuid", str(value)]
    if isinstance(value, bytes):
        return ["binary", value.hex()]
    if isinstance(value, float):
        return ["float", value.hex()]
    if isinstance(value, str):
        return ["string", value]
    if isinstance(value, list):
        return ["array", [canonical(item) for item in value]]
    if isinstance(value, dict):
        return ["object", [[key, canonical(value[key])] for key in sorted(value)]]
    raise ImportFailure("unsupported_canonical_value")


def read_rows(connection, table, target):
    columns = []
    for column in table.columns:
        target_column = target.c[column.name]
        if column_kind(target_column) == "json":
            columns.append(cast(column, Text).label(column.name))
        elif connection.dialect.name == "sqlite":
            # SQLite Numeric/Date processors can round or coerce stored values
            # before comparison. Preserve raw DB-API values from the snapshot.
            columns.append(type_coerce(column, NullType()).label(column.name))
        else:
            columns.append(column)
    rows = []
    for row in connection.execute(select(*columns)).mappings():
        rows.append({key: convert_value(value, target.c[key]) for key, value in row.items()})
    return rows


def fingerprint(rows):
    encoded = [
        json.dumps(
            {key: canonical(value) for key, value in row.items()},
            sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
        for row in rows
    ]
    digest = hashlib.sha256()
    for row in sorted(encoded):
        digest.update(len(row).to_bytes(8, "big"))
        digest.update(row)
    return digest.digest()


def validate_schema(source_tables, target_tables):
    if not source_tables:
        raise ImportFailure("source_has_no_tables")
    if set(source_tables) - set(target_tables):
        raise ImportFailure("source_tables_missing_in_target", details={"tables": sorted(set(source_tables) - set(target_tables))})
    for name, source in source_tables.items():
        target = target_tables[name]
        if set(source.c.keys()) - set(target.c.keys()):
            raise ImportFailure("source_columns_missing_in_target", details={"table": name, "columns": sorted(set(source.c.keys()) - set(target.c.keys()))})
        for column in target.columns:
            column_kind(column)
            if column.computed is not None and column.name in source.c:
                raise ImportFailure("generated_column_cannot_be_imported")
            if column.name not in source.c and (
                not column.nullable and column.server_default is None
                and column.identity is None and column.computed is None
            ):
                raise ImportFailure("required_target_column_missing_from_source", details={"table": name, "column": column.name, "type": type(column.type).__name__})
            if isinstance(column.type, JSON):
                column.type.none_as_null = True


def repair_sequences(connection, table):
    quote = connection.dialect.identifier_preparer.quote
    qualified = quote_table(connection, table)
    for column in table.columns:
        if not isinstance(column.type, Integer):
            continue
        sequence = connection.execute(
            text("SELECT pg_get_serial_sequence(:table_name, :column_name)"),
            {"table_name": qualified, "column_name": column.name},
        ).scalar()
        if not sequence:
            continue
        info = connection.execute(text(
            "SELECT n.nspname, c.relname, s.seqstart, s.seqincrement, s.seqmax "
            "FROM pg_sequence s JOIN pg_class c ON c.oid=s.seqrelid "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE c.oid=CAST(:sequence AS regclass)"
        ), {"sequence": sequence}).one()
        if info.seqincrement != 1:
            raise ImportFailure("unsupported_sequence_increment")
        highest = connection.execute(select(func.max(column))).scalar()
        next_value = max(int(info.seqstart), int(highest) + 1 if highest is not None else int(info.seqstart))
        if next_value > info.seqmax:
            raise ImportFailure("sequence_overflow")
        # ALTER ... RESTART is transactional; setval() is not rolled back.
        sequence_name = quote(info.nspname) + "." + quote(info.relname)
        connection.execute(text(f"ALTER SEQUENCE {sequence_name} RESTART WITH {next_value}"))


def migrate(source: Path, expected_sha256: str, destination, *, target_sha: str = ""):
    if destination.dialect.name != "postgresql":
        raise ImportFailure("postgresql_destination_required")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ImportFailure("invalid_expected_sha256")
    if not source.is_file() or source.is_symlink():
        raise ImportFailure("source_file_missing_or_symlink")
    if any(Path(str(source) + suffix).exists() for suffix in ("-wal", "-shm", "-journal")):
        raise ImportFailure("source_is_not_standalone_snapshot")
    if file_sha256(source) != expected_sha256:
        raise ImportFailure("source_sha256_mismatch")
    source_engine = create_engine(f"sqlite:///file:{source.resolve().as_posix()}?mode=ro&uri=true")
    committed = False
    try:
        with source_engine.connect() as origin:
            if origin.exec_driver_sql("PRAGMA quick_check").fetchall() != [("ok",)]:
                raise ImportFailure("source_integrity_failed")
            if origin.exec_driver_sql("PRAGMA foreign_key_check").first() is not None:
                raise ImportFailure("source_foreign_key_violation")
            source_metadata = MetaData()
            source_metadata.reflect(bind=origin)
            source_tables = {table.name: table for table in source_metadata.tables.values()}
            target_metadata = MetaData()
            with destination.begin() as target:
                target.execute(text("SET LOCAL lock_timeout = '5s'"))
                target.execute(text("SET LOCAL statement_timeout = '60s'"))
                target_metadata.reflect(bind=target, schema="public")
                target_tables = {table.name: table for table in target_metadata.tables.values()}
                validate_schema(source_tables, target_tables)
                for table in sorted(target_tables.values(), key=lambda item: item.name):
                    target.execute(text(f"LOCK TABLE {quote_table(target, table)} IN ACCESS EXCLUSIVE MODE"))
                    if target.execute(select(func.count()).select_from(table)).scalar_one():
                        raise ImportFailure("destination_not_empty")
                expected = {}
                counts = {}
                for table in target_metadata.sorted_tables:
                    if table.name not in source_tables:
                        continue
                    rows = read_rows(origin, source_tables[table.name], table)
                    expected[table.name] = fingerprint(rows)
                    counts[table.name] = len(rows)
                    if rows:
                        target.execute(table.insert(), rows)
                if not sum(counts.values()):
                    raise ImportFailure("source_has_no_rows")
                target.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
                for name in source_tables:
                    # Compare only source columns; target defaults are checked
                    # separately by PostgreSQL constraints and application smoke.
                    table = target_tables[name]
                    projected = select(*(table.c[column.name] for column in source_tables[name].columns)).subquery()
                    mirror = read_rows(target, projected, table)
                    if len(mirror) != counts[name] or fingerprint(mirror) != expected[name]:
                        raise ImportFailure("precommit_readback_mismatch")
                if file_sha256(source) != expected_sha256:
                    raise ImportFailure("source_changed_during_import")
                for table in target_tables.values():
                    repair_sequences(target, table)
            committed = True
            # Independent connection proves the committed data, not a view of
            # uncommitted rows from the importing transaction.
            with destination.connect() as readback:
                for name, source_table in source_tables.items():
                    table = target_tables[name]
                    projected = select(*(table.c[column.name] for column in source_table.columns)).subquery()
                    rows = read_rows(readback, projected, table)
                    if len(rows) != counts[name] or fingerprint(rows) != expected[name]:
                        raise ImportFailure("independent_readback_mismatch", committed=True)
            return {
                "schema_version": "1.0.0",
                "contract": "reqsys-sqlite-postgres-import",
                "status": "verified",
                "verified_at": datetime.now(timezone.utc).isoformat(),
                "target_sha": target_sha,
                "source_sha256": expected_sha256,
                "source_rows": sum(counts.values()),
                "copied_rows": sum(counts.values()),
                "table_counts": counts,
                "sqlite_integrity_ok": True,
                "source_foreign_keys_ok": True,
                "digests_match": True,
                "target_verified": True,
                "independent_readback": True,
                "sequences_restarted_transactionally": True,
                "migration_committed": True,
                "secrets_exposed": False,
                "production_touched": False,
                "database": {"schema": "public"},
            }
    except ImportFailure as error:
        error.committed = error.committed or committed
        raise
    except Exception:
        # SQLAlchemy/driver exception text may contain bound rows and credentials.
        raise ImportFailure("database_operation_failed", committed=committed) from None
    finally:
        source_engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    payload = {"schema_version": "1.0.0", "contract": "reqsys-sqlite-postgres-import", "status": "failed"}
    try:
        # Fixed trusted mount supplied by the reviewed Compose package.
        spec = importlib.util.spec_from_file_location("reqsys_start_api", "/opt/reqsys/start_api.py")
        if spec is None or spec.loader is None:
            raise ImportFailure("secret_loader_missing")
        loader = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loader)
        loader.configure(Path("/run/secrets"))
        url = os.environ["DATABASE_URL"]
        from sqlalchemy.engine import make_url
        identity = make_url(url)
        if (identity.get_backend_name(), identity.username, identity.host, identity.port, identity.database) != (
            "postgresql", "reqsys_app", "db", 5432, "reqsys"
        ):
            raise ImportFailure("destination_identity_mismatch")
        sha = os.environ.get("REQSYS_BUILD_SHA", "")
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ImportFailure("target_sha_missing_or_invalid")
        # Registers all current models and creates empty schema; no ASGI startup.
        import app.main  # noqa: F401
        engine = create_engine(url, hide_parameters=True)
        try:
            payload = migrate(SOURCE, args.expected_sha256, engine, target_sha=sha)
            payload["database"].update({"database": "reqsys", "role": "reqsys_app"})
        finally:
            engine.dispose()
    except ImportFailure as error:
        payload.update({"error_code": error.code, "migration_committed": error.committed, "details": error.details})
    except Exception:
        payload.update({"error_code": "import_preparation_failed", "migration_committed": False})
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    temporary = EVIDENCE.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(EVIDENCE)
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0 if payload["status"] == "verified" else 1


if __name__ == "__main__":
    sys.exit(main())
