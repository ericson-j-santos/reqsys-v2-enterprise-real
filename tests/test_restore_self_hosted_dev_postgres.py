"""Archive-bound PostgreSQL restore checks; real contract runs on disposable GitHub CI only."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/restore_self_hosted_dev_postgres.py"
spec = importlib.util.spec_from_file_location("reqsys_pg_restore", SCRIPT)
restore = importlib.util.module_from_spec(spec)
spec.loader.exec_module(restore)


DATA = (
    b"SET client_encoding = 'UTF8';\n"
    b"SELECT pg_catalog.set_config('search_path', '', false);\n"
    b"\\restrict token123\n"
    b'COPY public.items (id, value) FROM stdin;\n'
    b"1\tone\\ttwo\\nthree\n"
    b"2\t\\N\n"
    b"\\.\n"
    b"SELECT pg_catalog.setval('public.items_id_seq', 3, true);\n"
    b"\\unrestrict token123\n"
)
TOC = (
    b"1; 2615 2200 SCHEMA - public pg_database_owner\n"
    b"2; 0 0 COMMENT - SCHEMA public pg_database_owner\n"
    b"3; 1259 123 TABLE public items reqsys_app\n"
    b"4; 1259 124 SEQUENCE public items_id_seq reqsys_app\n"
    b"5; 0 0 SEQUENCE OWNED BY public items_id_seq reqsys_app\n"
    b"6; 0 123 TABLE DATA public items reqsys_app\n"
    b"7; 0 0 SEQUENCE SET public items_id_seq reqsys_app\n"
)


class ArchiveTests(unittest.TestCase):
    def test_copy_digest_counts_and_sequence_are_bound_to_archive(self):
        tables, sequences = restore.parse_archive_data(DATA)
        self.assertEqual(tables["items"]["count"], 2)
        self.assertEqual(tables["items"]["columns"], ("id", "value"))
        self.assertEqual(tables["items"]["digest"], restore.digest_rows([
            b"1\tone\\ttwo\\nthree", b"2\t\\N",
        ]))
        self.assertEqual(sequences, {"items_id_seq": ("3", True)})

    def test_row_order_is_irrelevant_but_multiplicity_is_not(self):
        self.assertEqual(restore.digest_rows([b"a", b"b"]), restore.digest_rows([b"b", b"a"]))
        self.assertNotEqual(restore.digest_rows([b"a"]), restore.digest_rows([b"a", b"a"]))

    def test_copy_record_carriage_returns_are_not_record_separators(self):
        raw = b"COPY public.items (value) FROM stdin;\na\rb\vc\n\\.\n"
        table, _ = restore.parse_archive_data(raw)
        self.assertEqual(table["items"]["count"], 1)
        self.assertEqual(table["items"]["digest"], restore.digest_rows([b"a\rb\vc"]))

    def test_missing_copy_terminator_rejected(self):
        with self.assertRaises(restore.RestoreError):
            restore.parse_archive_data(DATA.replace(b"\\.\n", b""))

    def test_duplicate_table_rejected(self):
        with self.assertRaises(restore.RestoreError):
            restore.parse_archive_data(DATA + DATA)

    def test_insert_and_foreign_namespace_are_not_silently_skipped(self):
        for raw in (
            b"INSERT INTO public.items VALUES ('secret');\n",
            b"COPY other.items (id) FROM stdin;\n1\n\\.\n",
            b"SELECT lo_create(123);\n",
        ):
            with self.assertRaises(restore.RestoreError):
                restore.parse_archive_data(raw)

    def test_copy_row_width_and_identifiers_checked(self):
        for raw in (
            b"COPY public.items (id,value) FROM stdin;\n1\n\\.\n",
            b"COPY public.items (id,id) FROM stdin;\n1\t2\n\\.\n",
            b'COPY public.items ("id", evil;drop) FROM stdin;\n1\t2\n\\.\n',
        ):
            with self.assertRaises(restore.RestoreError):
                restore.parse_archive_data(raw)

    def test_toc_includes_sequence_owned_and_set_entries(self):
        tables, data, sequences = restore.parse_toc(TOC)
        self.assertEqual(tables, {"items"})
        self.assertEqual(data, {"items"})
        self.assertEqual(sequences, {"items_id_seq"})

    def test_unsupported_archive_relation_kinds_rejected_before_restore(self):
        for kind in ("VIEW", "MATERIALIZED VIEW", "FOREIGN TABLE", "TABLE ATTACH"):
            with self.assertRaises(restore.RestoreError):
                restore.parse_toc(TOC + ("8; 0 555 " + kind + " public other reqsys_app\n").encode())

    def test_toc_missing_table_data_rejected(self):
        with self.assertRaises(restore.RestoreError):
            restore.parse_toc(TOC.replace(b"6; 0 123 TABLE DATA public items reqsys_app\n", b""))

    def test_manifest_omits_only_preexisting_public_schema_metadata(self):
        value = restore.restore_list(TOC)
        self.assertNotIn(b"SCHEMA - public", value)
        self.assertNotIn(b"COMMENT - SCHEMA public", value)
        self.assertIn(b"TABLE public items", value)
        self.assertIn(b"TABLE DATA public items", value)
        self.assertIn(b"SEQUENCE SET", value)

    def test_foreign_schema_manifest_rejected(self):
        with self.assertRaises(restore.RestoreError):
            restore.restore_list(TOC + b"8; 2615 456 SCHEMA - unrelated reqsys_app\n")

    def backup(self, encrypted=b"protected", archive=b"PGDMPfixture"):
        return {
            "schema_version": "1.0.0",
            "contract": "reqsys-current-dev-postgres-protected-backup",
            "status": "captured",
            "source": {
                "host": restore.HOST, "project": restore.SOURCE_PROJECT,
                "api_container_id": "a" * 64, "db_container_id": "b" * 64,
                "build_sha": "c" * 40, "database": "reqsys",
                "role": "reqsys_app", "system_identifier": "123",
            },
            "archive": {
                "format": "postgresql_custom", "size_bytes": len(archive),
                "sha256": hashlib.sha256(archive).hexdigest(),
            },
            "protection": {
                "kind": "windows-dpapi-current-user", "entropy": "none",
                "encrypted_size_bytes": len(encrypted),
                "encrypted_sha256": hashlib.sha256(encrypted).hexdigest(),
            },
        }

    def test_backup_requires_exact_source_and_both_file_hashes(self):
        encrypted, archive = b"protected", b"PGDMPfixture"
        proof = self.backup(encrypted, archive)
        self.assertEqual(restore.validate_backup(proof, encrypted, archive)["project"], restore.SOURCE_PROJECT)
        for changed in ("project", "database", "role"):
            corrupt = json.loads(json.dumps(proof))
            corrupt["source"][changed] = "other"
            with self.assertRaises(restore.RestoreError):
                restore.validate_backup(corrupt, encrypted, archive)
        for corrupted in (encrypted + b"x",):
            with self.assertRaises(restore.RestoreError):
                restore.validate_backup(proof, corrupted, archive)
        with self.assertRaises(restore.RestoreError):
            restore.validate_backup(proof, encrypted, archive + b"x")

    def test_duplicate_json_key_rejected(self):
        with self.assertRaises(restore.RestoreError):
            restore.json_bytes(b'{"status":"captured","status":"verified"}')

    def test_non_windows_dpapi_rejected(self):
        with patch.object(restore.os, "name", "posix"):
            with self.assertRaises(restore.RestoreError):
                restore.decrypt_current_user(restore.HEADER + b"cipher")

    def test_process_error_never_exposes_stderr(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(restore.RestoreError) as error:
                restore.bounded_run(
                    ["unavailable-reqsys-command"], b"", Path(folder), 1024, 1,
                )
            self.assertEqual(str(error.exception), "database_command_unavailable")

    def test_subprocess_output_limit_is_enforced(self):
        fake = SimpleNamespace(
            stdin=SimpleNamespace(write=lambda data: None, close=lambda: None),
            stdout=SimpleNamespace(read=lambda size: b"x" * (1025 if size else 0), close=lambda: None),
            wait=lambda timeout: 0, kill=lambda: None,
        )
        with patch.object(restore.subprocess, "Popen", return_value=fake):
            with self.assertRaises(restore.RestoreError) as error:
                restore.bounded_run(["fake"], b"", Path("."), 1024, 1)
        self.assertEqual(str(error.exception), "database_command_failed")

    def test_activation_rejects_sqlite_proof(self):
        proof = {"schema_version": "1", "contract": "reqsys-sqlite-postgres-import"}
        with self.assertRaises(restore.RestoreError):
            restore.validate_restore_proof(proof, "a" * 40, {}, "b" * 64, datetime.now(timezone.utc))

    def test_existing_proof_is_preserved_before_any_database_restore(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "restore-proof.json").write_text('{"old":true}')
            publisher = SimpleNamespace(root=root, private=SimpleNamespace(), require_key_handoff=lambda source: {})
            restorer = restore.Restorer(publisher)
            identity = {"container_id": "d" * 64}
            def binary(program, args, payload, *extra):
                return TOC if "--list" in args else DATA
            proof = self.backup()
            proof["archive"]["toc_table_data_count"] = 1
            with (
                patch.object(restorer, "owned_inactive", return_value=identity),
                patch.object(restorer, "binary", side_effect=binary) as called,
                patch.object(restore, "check_backup_acl"),
                patch.object(restore, "read_private", side_effect=[b"protected", json.dumps(proof).encode()]),
                patch.object(restore, "decrypt_current_user", return_value=b"PGDMPfixture"),
                patch.dict(restore.os.environ, {"LOCALAPPDATA": folder}),
            ):
                with self.assertRaises(restore.RestoreError) as error:
                    restorer.restore()
            self.assertEqual(str(error.exception), "existing_restore_proof_preserved")
            self.assertTrue(all("--dbname=reqsys" not in call.args[1] for call in called.call_args_list))
            self.assertEqual((root / "restore-proof.json").read_text(), '{"old":true}')

    def test_publisher_activation_rejects_invalid_postgres_proof_before_build(self):
        publish = restore.load_publisher()
        publisher = object.__new__(publish.Publisher)
        publisher.validate_source = lambda: None
        publisher.validate_engine = lambda: None
        publisher.configure = lambda: ("tenant", "client")
        publisher.require_owned_project = lambda: None
        verifier = SimpleNamespace(
            RestoreError=restore.RestoreError,
            verify_existing=lambda publisher, sha: (_ for _ in ()).throw(
                restore.RestoreError("restore_proof_binding_invalid")),
        )
        publisher.postgres_restorer_module = lambda: verifier
        with patch.object(publisher, "compose") as compose:
            with self.assertRaises(publish.PublishError) as error:
                publisher.activate("b" * 64)
        self.assertEqual(error.exception.code, "postgres_restore_proof_binding_invalid")
        compose.assert_not_called()

    def test_publisher_postgres_restore_returns_only_sanitized_summary(self):
        publish = restore.load_publisher()
        publisher = object.__new__(publish.Publisher)
        restorer = SimpleNamespace(restore=lambda: {
            "copied_rows": 4, "private_archive_content": {"secret": "should-not-return"},
        })
        module = SimpleNamespace(RestoreError=restore.RestoreError, Restorer=lambda publisher: restorer)
        publisher.postgres_restorer_module = lambda: module
        result = publisher.restore_postgres()
        self.assertEqual(result["restored_rows"], 4)
        self.assertFalse(result["application_started"])
        self.assertFalse(result["usable"])
        self.assertNotIn("private_archive_content", result)

    def test_live_api_or_gateway_blocks_restore(self):
        publisher = SimpleNamespace(
            validate_source=lambda: None, validate_engine=lambda: None,
            require_owned_project=lambda: None, root=Path("."), private=None,
            run=lambda name, args: "123456789abc" if name == "postgres_project_running" else json.dumps(
                {"com.docker.compose.service": "api"}),
        )
        with self.assertRaises(restore.RestoreError) as error:
            restore.Restorer(publisher).owned_inactive()
        self.assertEqual(str(error.exception), "candidate_application_already_running")


@unittest.skipUnless(
    os.name == "posix"
    and os.environ.get("GITHUB_ACTIONS") == "true"
    and os.environ.get("REQSYS_POSTGRES_RESTORE_CONTRACT") == "1"
    and os.environ.get("REQSYS_TEST_PG_CONTAINER"),
    "real PostgreSQL restore contract requires disposable GitHub CI service",
)
class RealPostgresContract(unittest.TestCase):
    """Archive COPY digests and sequences survive a real PostgreSQL16 restore."""

    def test_archive_restore_readback_detects_content_mutation(self):
        container = os.environ["REQSYS_TEST_PG_CONTAINER"]
        self.assertRegex(container, r"^[a-f0-9]{12,64}$")

        def exec_sql(database, text):
            return restore.bounded_run([
                "docker", "exec", "-i", container, "psql", "--no-psqlrc",
                "--quiet", "--tuples-only", "--no-align", "--set=ON_ERROR_STOP=1",
                "--username=postgres", "--dbname=" + database,
            ], text.encode(), Path("."), restore.MAX_OUTPUT, 60)

        source = "reqsys_pg_restore_source"
        target = "reqsys_pg_restore_contract"
        role_exists = exec_sql("postgres", "SELECT 1 FROM pg_roles WHERE rolname='reqsys_app';\n").strip() == b"1"
        if not role_exists:
            exec_sql("postgres", "CREATE ROLE reqsys_app NOSUPERUSER NOCREATEDB NOCREATEROLE;\n")
        role = restore.json_bytes(exec_sql("postgres", "SELECT json_build_array(rolsuper,rolcreatedb,rolcreaterole) FROM pg_roles WHERE rolname='reqsys_app';\n"))
        self.assertEqual(role, [False, False, False])
        exec_sql("postgres", "CREATE DATABASE " + source + ";\nCREATE DATABASE " + target + ";\n")
        try:
            exec_sql(source, """
CREATE TYPE public.status AS ENUM ('new','old');
CREATE TABLE public.items (
 id bigserial PRIMARY KEY, value text, payload jsonb, created timestamptz,
 amount numeric(24,8), data bytea, status public.status NOT NULL DEFAULT 'new',
 CONSTRAINT positive_amount CHECK (amount >= 0)
);
INSERT INTO public.items(value,payload,created,amount,data) VALUES
 (E'one\\ttwo\\nthree','{"key":[1,null,true]}','2026-10-03T00:00:00Z',123456789.12345678,'\\x00ff'),
 (NULL,'null','2026-10-03T02:00:00+02:00',0,NULL);
CREATE TABLE public.empty_table (id integer, value text);
SELECT setval('public.items_id_seq',100,true);
""")
            exec_sql(target, "GRANT USAGE, CREATE ON SCHEMA public TO reqsys_app;\n")
            archive = restore.bounded_run([
                "docker", "exec", container, "pg_dump", "--format=custom",
                "--compress=0", "--username=postgres", "--dbname=" + source,
            ], b"", Path("."), restore.MAX_ARCHIVE, 60)
            publisher = SimpleNamespace(
                source=Path("."), root=Path("."), private=None, events=[],
            )
            restorer = restore.Restorer(publisher)
            restorer.db = container
            restorer.sql = lambda sql, limit=restore.MAX_PROOF: exec_sql(target, sql)
            toc = restorer.binary("pg_restore", ["--list"], archive, restore.MAX_PROOF)
            toc_tables, toc_data, toc_sequences = restore.parse_toc(toc)
            tables, sequences = restore.parse_archive_data(restorer.binary(
                "pg_restore", ["--data-only", "--no-owner", "--no-privileges", "--file=-"], archive,
            ))
            self.assertEqual(set(tables), toc_data)
            self.assertEqual(set(sequences), toc_sequences)
            self.assertEqual(toc_tables, {"items", "empty_table"})
            manifest_path = "/tmp/reqsys-ci-pg-restore.list"
            manifest = restore.restore_list(toc)
            written = restore.bounded_run(
                ["docker", "exec", "-i", container, "tee", manifest_path],
                manifest, Path("."), restore.MAX_PROOF, 30,
            )
            self.assertEqual(written, manifest)
            restorer.binary("pg_restore", [
                "--exit-on-error", "--single-transaction", "--no-owner", "--no-privileges",
                "--role=reqsys_app", "--username=postgres", "--dbname=" + target,
                "--use-list=" + manifest_path,
            ], archive, restore.MAX_PROOF, 60)
            restorer.committed = True
            schema = restorer.verify(tables, sequences)
            self.assertEqual({name: entry["count"] for name, entry in tables.items()}, {
                "items": 2, "empty_table": 0,
            })
            self.assertTrue(schema["tables"])
            exec_sql(target, "UPDATE public.items SET value='changed' WHERE id=1;\n")
            with self.assertRaises(restore.RestoreError) as error:
                restorer.verify(tables, sequences)
            self.assertEqual(error.exception.code, "archive_content_readback_mismatch")
            self.assertTrue(error.exception.committed)
        finally:
            exec_sql("postgres", "DROP DATABASE " + source + ";\nDROP DATABASE " + target + ";\n")
            if not role_exists:
                exec_sql("postgres", "DROP ROLE reqsys_app;\n")
            restore.bounded_run(
                ["docker", "exec", container, "rm", "-f", "--", "/tmp/reqsys-ci-pg-restore.list"],
                b"", Path("."), 4096, 30,
            )
