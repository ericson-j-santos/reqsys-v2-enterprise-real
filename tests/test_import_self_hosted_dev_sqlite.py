"""Tests avoid application import and use disposable PostgreSQL CI databases."""
from __future__ import annotations

import importlib.util
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import Column, Integer, JSON, MetaData, String, Table, Boolean, Numeric, DateTime, create_engine, select, text
from sqlalchemy.engine import make_url

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "import_self_hosted_dev_sqlite.py"
spec = importlib.util.spec_from_file_location("self_hosted_sqlite_import", MODULE_PATH)
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


@pytest.fixture
def postgres():
    raw = os.environ.get("REQSYS_IMPORTER_TEST_DATABASE_URL")
    if not raw:
        pytest.skip("disposable PostgreSQL service not configured")
    url = make_url(raw)
    if url.host not in {"127.0.0.1", "localhost"} or url.database != "reqsys_importer_test":
        pytest.fail("PostgreSQL test service must be localhost / reqsys_importer_test")
    # Never reset a supplied existing database. Create and delete a unique child.
    database = "reqsys_importer_test_" + uuid.uuid4().hex
    admin = create_engine(url, isolation_level="AUTOCOMMIT", hide_parameters=True)
    with admin.connect() as connection:
        if connection.execute(text("SELECT current_database()")).scalar_one() != "reqsys_importer_test":
            pytest.fail("test database identity mismatch")
        connection.execute(text(f'CREATE DATABASE "{database}"'))
    engine = create_engine(url.set(database=database), hide_parameters=True)
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{database}" WITH (FORCE)'))
        admin.dispose()


def snapshot(tmp_path, ddl, rows):
    path = tmp_path / "source.db"
    with sqlite3.connect(path) as connection:
        connection.executescript(ddl)
        for statement, values in rows:
            connection.executemany(statement, values)
    return path, migration.file_sha256(path)


def target_schema(postgres, *, child=False, required_extra=False):
    metadata = MetaData()
    columns = [
        Column("id", Integer, primary_key=True),
        Column("title", String(50), nullable=False),
        Column("active", Boolean, nullable=False),
        Column("amount", Numeric(12, 2), nullable=False),
        Column("payload", JSON, nullable=True),
    ]
    if required_extra:
        columns.append(Column("required_extra", String, nullable=False))
    parent = Table("items", metadata, *columns)
    if child:
        from sqlalchemy import ForeignKey
        Table("children", metadata, Column("id", Integer, primary_key=True),
              Column("item_id", Integer, ForeignKey("items.id"), nullable=False))
    metadata.create_all(postgres)
    return parent


def item_snapshot(tmp_path):
    return snapshot(
        tmp_path,
        "CREATE TABLE items(id INTEGER PRIMARY KEY, title TEXT NOT NULL, active INTEGER NOT NULL,"
        "amount NUMERIC NOT NULL, payload TEXT);",
        [("INSERT INTO items VALUES (?, ?, ?, ?, ?)", [
            (10, "example-a", 1, "12.30", '{"b":[1,true],"a":null}'),
            (40, "example-b", 0, "0.01", None),
            (41, "example-c", 1, "4.00", "null"),
        ])],
    )


def test_import_counts_digests_json_null_and_sequences(tmp_path, postgres):
    parent = target_schema(postgres)
    path, digest = item_snapshot(tmp_path)
    evidence = migration.migrate(path, digest, postgres, target_sha="a" * 40)
    assert evidence["status"] == "verified"
    assert evidence["table_counts"] == {"items": 3}
    assert evidence["independent_readback"] is True
    assert evidence["digests_match"] is True
    assert evidence["source_rows"] == evidence["copied_rows"] == 3
    with postgres.begin() as connection:
        assert connection.execute(text("SELECT payload IS NULL FROM items WHERE id=40")).scalar_one() is True
        assert connection.execute(text("SELECT payload::text FROM items WHERE id=41")).scalar_one() == "null"
        inserted = connection.execute(parent.insert().values(
            title="later", active=True, amount=Decimal("1.00"), payload={}
        )).inserted_primary_key[0]
        assert inserted == 42
    assert migration.file_sha256(path) == digest


def test_nonempty_destination_is_preserved(tmp_path, postgres):
    table = target_schema(postgres)
    with postgres.begin() as connection:
        connection.execute(table.insert().values(id=1, title="existing", active=True, amount=1, payload={}))
    path, digest = item_snapshot(tmp_path)
    with pytest.raises(migration.ImportFailure, match="destination_not_empty"):
        migration.migrate(path, digest, postgres)
    with postgres.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM items")).scalar_one() == 1


def test_unknown_table_is_not_silently_dropped(tmp_path, postgres):
    target_schema(postgres)
    path, digest = snapshot(tmp_path, "CREATE TABLE legacy_only(id INTEGER PRIMARY KEY);",
                            [("INSERT INTO legacy_only VALUES (?)", [(1,)])])
    with pytest.raises(migration.ImportFailure, match="source_tables_missing_in_target") as caught:
        migration.migrate(path, digest, postgres)
    assert caught.value.details["tables"] == ["legacy_only"]
    with postgres.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM items")).scalar_one() == 0


def test_unknown_column_and_missing_required_column_fail_before_copy(tmp_path, postgres):
    target_schema(postgres, required_extra=True)
    path, digest = item_snapshot(tmp_path)
    with pytest.raises(migration.ImportFailure, match="required_target_column_missing_from_source"):
        migration.migrate(path, digest, postgres)
    with sqlite3.connect(path) as connection:
        connection.execute("ALTER TABLE items ADD COLUMN unexpected TEXT")
    with pytest.raises(migration.ImportFailure, match="source_columns_missing_in_target"):
        migration.migrate(path, migration.file_sha256(path), postgres)
    with postgres.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM items")).scalar_one() == 0


def test_later_foreign_key_failure_rolls_back_earlier_rows(tmp_path, postgres):
    target_schema(postgres, child=True)
    path, digest = snapshot(
        tmp_path,
        "CREATE TABLE items(id INTEGER PRIMARY KEY, title TEXT NOT NULL, active INTEGER NOT NULL,"
        "amount NUMERIC NOT NULL, payload TEXT);"
        "CREATE TABLE children(id INTEGER PRIMARY KEY, item_id INTEGER NOT NULL);",
        [("INSERT INTO items VALUES (?, ?, ?, ?, ?)", [(10, "private-value-should-not-appear", 1, 5, "{}")]),
         ("INSERT INTO children VALUES (?, ?)", [(1, 999)])],
    )
    with pytest.raises(migration.ImportFailure, match="database_operation_failed") as caught:
        migration.migrate(path, digest, postgres)
    assert "private-value" not in str(caught.value)
    assert caught.value.committed is False
    with postgres.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM items")).scalar_one() == 0
        assert connection.execute(text("SELECT count(*) FROM children")).scalar_one() == 0


def test_readback_catches_numeric_rounding_and_rolls_back(tmp_path, postgres):
    target_schema(postgres)
    path, digest = snapshot(
        tmp_path,
        "CREATE TABLE items(id INTEGER PRIMARY KEY, title TEXT NOT NULL, active INTEGER NOT NULL,"
        "amount NUMERIC NOT NULL, payload TEXT);",
        [("INSERT INTO items VALUES (?, ?, ?, ?, ?)", [(20, "rounded", 1, "1.2345", "{}")])],
    )
    with pytest.raises(migration.ImportFailure, match="precommit_readback_mismatch"):
        migration.migrate(path, digest, postgres)
    with postgres.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM items")).scalar_one() == 0


def test_sequence_changes_rollback_with_transaction(tmp_path, postgres, monkeypatch):
    table = target_schema(postgres)
    path, digest = item_snapshot(tmp_path)
    original = migration.repair_sequences

    def repair_then_fail(connection, target):
        original(connection, target)
        raise migration.ImportFailure("forced_after_sequence_restart")
    monkeypatch.setattr(migration, "repair_sequences", repair_then_fail)
    with pytest.raises(migration.ImportFailure, match="forced_after_sequence_restart"):
        migration.migrate(path, digest, postgres)
    with postgres.begin() as connection:
        assert connection.execute(text("SELECT count(*) FROM items")).scalar_one() == 0
        result = connection.execute(table.insert().values(title="after-failure", active=True, amount=1, payload={}))
        assert result.inserted_primary_key[0] == 1


def test_wrong_hash_makes_no_destination_changes(tmp_path, postgres):
    target_schema(postgres)
    path, _ = item_snapshot(tmp_path)
    with pytest.raises(migration.ImportFailure, match="source_sha256_mismatch"):
        migration.migrate(path, "0" * 64, postgres)
    with postgres.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM items")).scalar_one() == 0


@pytest.mark.parametrize("value,error", [(2, "invalid_boolean"), ("false", "invalid_boolean")])
def test_boolean_conversion_is_strict(value, error):
    with pytest.raises(migration.ImportFailure, match=error):
        migration.convert_value(value, Column("active", Boolean))


@pytest.mark.parametrize("value,error", [
    ('{"a":1,"a":2}', "duplicate_json_object_key"),
    ('{"n":1.234567890123456789}', "json_numeric_precision_loss"),
    ('{"n":NaN}', "json_numeric_precision_loss"),
])
def test_json_does_not_drop_keys_or_numeric_precision(value, error):
    with pytest.raises(migration.ImportFailure, match=error):
        migration.convert_value(value, Column("payload", JSON))


def test_timezone_conversion_requires_explicit_compatible_semantics():
    with pytest.raises(migration.ImportFailure, match="temporal_timezone_mismatch"):
        migration.convert_value(datetime(2026, 1, 1), Column("when", DateTime(timezone=True)))
    aware = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert migration.convert_value(aware, Column("when", DateTime(timezone=True))) == aware



def test_sqlite_numeric_read_keeps_integer_precision_and_long_fraction(tmp_path, postgres):
    metadata = MetaData()
    Table("precise", metadata, Column("id", Integer, primary_key=True),
          Column("amount", Numeric(35, 15), nullable=False))
    metadata.create_all(postgres)
    path, digest = snapshot(
        tmp_path,
        "CREATE TABLE precise(id INTEGER PRIMARY KEY, amount NUMERIC NOT NULL);",
        [("INSERT INTO precise VALUES (?, ?)", [(1, 9007199254740993), (2, "0.123456789012345")])],
    )
    evidence = migration.migrate(path, digest, postgres)
    assert evidence["table_counts"] == {"precise": 2}
    with postgres.connect() as connection:
        amounts = connection.execute(text("SELECT amount FROM precise ORDER BY id")).scalars().all()
        assert amounts == [Decimal("9007199254740993"), Decimal("0.123456789012345")]


@pytest.mark.parametrize("scalar,object_value", [
    (None, {"sql_null": True}),
    (migration.JSON.NULL, {"json": None}),
    (1.0, {"float": 1.0.hex()}),
])
def test_fingerprint_cannot_confuse_user_json_with_typed_scalars(scalar, object_value):
    assert migration.fingerprint([{"payload": scalar}]) != migration.fingerprint([{"payload": object_value}])


def test_decimal_fingerprints_do_not_round_at_default_context_precision():
    left = Decimal("1234567890123456789012345678901")
    right = Decimal("1234567890123456789012345678902")
    assert migration.fingerprint([{"n": left}]) != migration.fingerprint([{"n": right}])
    assert migration.fingerprint([{"n": Decimal("1.2300")}]) == migration.fingerprint([{"n": Decimal("1.23")}])


def test_integer_to_float_refuses_loss_of_precision():
    from sqlalchemy import Float
    with pytest.raises(migration.ImportFailure, match="float_precision_loss"):
        migration.convert_value(9007199254740993, Column("number", Float))
