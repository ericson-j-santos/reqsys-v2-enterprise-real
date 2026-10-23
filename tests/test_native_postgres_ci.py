"""Offline unit tests; subprocess execution is forbidden throughout each test."""

from __future__ import annotations

import contextlib
import io
import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import native_postgres_ci as pg


class NativePostgresUnitTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="native-pg-unit-")
        self.addCleanup(temporary.cleanup)
        self.temp = Path(temporary.name).resolve()
        self.workspace = self.temp / "workspace"
        self.workspace.mkdir()
        environment = {
            "GITHUB_ACTIONS": "true", "GITHUB_RUN_ID": "123",
            "GITHUB_RUN_ATTEMPT": "2", "GITHUB_JOB": "backend-test",
            "GITHUB_SHA": "a" * 40, "GITHUB_WORKSPACE": str(self.workspace),
            "RUNNER_TEMP": str(self.temp), "ImageVersion": "unit-test-only",
        }
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, environment).start()
        self.no_subprocess = patch.object(
            pg.subprocess, "run", side_effect=AssertionError("offline_subprocess_forbidden")
        ).start()
        self.state_path = self.temp / "state.json"
        self.env_file = self.temp / "exports.env"

    def make_state(self):
        root = self.temp / "reqsys-pg16-test"
        root.mkdir(mode=0o700)
        (root / "data").mkdir(mode=0o700)
        (root / "socket").mkdir(mode=0o700)
        state = {
            "schema_version": "1.0", "root": str(root), "uid": os.geteuid(),
            "context": pg.context(), "instance_id": "unit-instance",
            "port": 54321, "versions": {name: "16.15" for name in pg.TOOLS},
            "state_path": str(self.state_path), "env_file": str(self.env_file),
        }
        encoded = json.dumps(state)
        pg.private_file(root / "owner.json", encoded)
        pg.private_file(self.state_path, encoded)
        pg.private_file(root / "pgpass", "127.0.0.1:54321:*:reqsys_app:unit-password\n")
        pg.private_file(self.env_file, "export DATABASE_URL=unit-only\n")
        return state

    def test_root_is_rejected_before_side_effects(self):
        with patch.object(pg.os, "geteuid", return_value=0):
            with self.assertRaisesRegex(pg.FixtureError, "non_root_required"):
                pg.require_runtime()
        self.no_subprocess.assert_not_called()

    def test_missing_or_invalid_ci_context_is_rejected(self):
        for updates in ({"GITHUB_SHA": "not-a-sha"}, {"GITHUB_RUN_ID": ""}):
            with self.subTest(updates=updates), patch.dict(os.environ, updates):
                with self.assertRaises(pg.FixtureError):
                    pg.context()

    def test_toolchain_accepts_only_consistent_major_16(self):
        regular_root_binary = type("Info", (), {"st_mode": stat.S_IFREG | 0o755, "st_uid": 0})()
        with patch.object(Path, "lstat", return_value=regular_root_binary), \
                patch.object(pg.os, "access", return_value=True), \
                patch.object(pg, "command") as command:
            command.return_value = subprocess.CompletedProcess([], 0, "psql (PostgreSQL) 16.15\n", "")
            self.assertEqual(set(pg.verify_binaries().values()), {"16.15"})
            command.return_value.stdout = "psql (PostgreSQL) 17.0\n"
            with self.assertRaisesRegex(pg.FixtureError, "major_16_required"):
                pg.verify_binaries()

    def test_mixed_minor_toolchain_fails_closed(self):
        info = type("Info", (), {"st_mode": stat.S_IFREG | 0o755, "st_uid": 0})()
        outputs = [subprocess.CompletedProcess([], 0, f"tool (PostgreSQL) {version}\n", "")
                   for version in ("16.15", "16.14", "16.15", "16.15", "16.15")]
        with patch.object(Path, "lstat", return_value=info), \
                patch.object(pg.os, "access", return_value=True), \
                patch.object(pg, "command", side_effect=outputs):
            with self.assertRaisesRegex(pg.FixtureError, "mixed_postgresql_toolchain"):
                pg.verify_binaries()

    def test_private_file_uses_0600_and_refuses_overwrite_or_symlink(self):
        target = self.temp / "secret"
        pg.private_file(target, "unit-test-only")
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        with self.assertRaises(FileExistsError):
            pg.private_file(target, "replacement")
        link = self.temp / "link"
        link.symlink_to(target)
        with self.assertRaises(OSError):
            pg.private_file(link, "replacement", exclusive=False)
        self.assertEqual(target.read_text(), "unit-test-only")

    def test_state_requires_exact_ci_context_and_ownership_marker(self):
        state = self.make_state()
        with patch.object(pg, "require_runtime", return_value=self.temp):
            self.assertEqual(pg.load_state(self.state_path), state)
            with patch.dict(os.environ, {"GITHUB_RUN_ATTEMPT": "3"}):
                with self.assertRaisesRegex(pg.FixtureError, "foreign_ci_context"):
                    pg.load_state(self.state_path)
            marker = Path(state["root"]) / "owner.json"
            pg.private_file(marker, "{}", exclusive=False)
            with self.assertRaisesRegex(pg.FixtureError, "ownership_marker_mismatch"):
                pg.load_state(self.state_path)

    def test_world_readable_state_is_rejected(self):
        self.make_state()
        self.state_path.chmod(0o644)
        with patch.object(pg, "require_runtime", return_value=self.temp):
            with self.assertRaisesRegex(pg.FixtureError, "private_permissions_required"):
                pg.load_state(self.state_path)

    def test_foreign_root_is_rejected_before_stop_or_delete(self):
        state = self.make_state()
        state["root"] = str(self.temp / "not-an-owned-cluster")
        pg.private_file(self.state_path, json.dumps(state), exclusive=False)
        with patch.object(pg, "require_runtime", return_value=self.temp), \
                patch.object(pg, "stop_server") as stop, \
                patch.object(pg.shutil, "rmtree") as remove:
            with self.assertRaisesRegex(pg.FixtureError, "foreign_cluster_path"):
                pg.cleanup(self.state_path)
            stop.assert_not_called()
            remove.assert_not_called()

    def test_probe_checks_identity_select_one_and_server_version(self):
        state = self.make_state()
        data = Path(state["root"]) / "data"
        good = f"{data}|160015|1|127.0.0.1|54321|reqsys_app|reqsys_test\n"
        with patch.object(pg, "is_ready", return_value=0), patch.object(pg, "sql") as sql:
            sql.side_effect = [subprocess.CompletedProcess([], 0, good, ""),
                               subprocess.CompletedProcess([], 0, "t\n", "")]
            self.assertEqual(pg.probe(state), 160015)
            for bad in (good.replace("160015", "170000"),
                        good.replace(str(data), "/var/lib/postgresql/16/main"),
                        good.replace("|1|", "|0|"),
                        good.replace("|54321|", "|5432|")):
                sql.side_effect = [subprocess.CompletedProcess([], 0, bad, "")]
                with self.assertRaises(pg.FixtureError):
                    pg.probe(state)

    def test_probe_rejects_non_scram_verifier(self):
        state = self.make_state()
        result = f"{state['root']}/data|160015|1|127.0.0.1|54321|reqsys_app|reqsys_test"
        with patch.object(pg, "is_ready", return_value=0), \
                patch.object(pg, "sql", side_effect=[
                    subprocess.CompletedProcess([], 0, result, ""),
                    subprocess.CompletedProcess([], 0, "f\n", "")]):
            with self.assertRaisesRegex(pg.FixtureError, "scram_verifier_required"):
                pg.probe(state)

    def test_stopped_probe_is_failure_not_sqlite_fallback(self):
        state = self.make_state()
        with patch.object(pg, "is_ready", return_value=2), patch.object(pg, "sql") as sql:
            with self.assertRaisesRegex(pg.FixtureError, "postgres_not_ready"):
                pg.probe(state)
            sql.assert_not_called()

    def test_sql_never_passes_password_in_argv_or_url(self):
        state = self.make_state()
        with patch.object(pg, "command") as command:
            pg.sql(state, "SELECT 1;")
        args, kwargs = command.call_args
        self.assertEqual(args[0], "psql")
        self.assertIn("-X", args[1])
        self.assertIn("-w", args[1])
        self.assertNotIn("unit-password", repr((args, kwargs)))
        self.assertEqual(set(kwargs["env"]), {"PGPASSFILE"})

    def test_command_scrubs_inherited_pg_connection_settings_and_redacts_failure(self):
        self.no_subprocess.side_effect = None
        self.no_subprocess.return_value = subprocess.CompletedProcess([], 2, "", "unit-secret")
        with patch.dict(os.environ, {"PGPASSWORD": "inherited", "PGHOST": "external.invalid",
                                     "PGSERVICE": "foreign", "DATABASE_URL": "sqlite:///bad"}):
            with self.assertRaisesRegex(pg.FixtureError, "psql_failed_exit_2") as caught:
                pg.command("psql", ["--version"])
        self.assertNotIn("unit-secret", str(caught.exception))
        env = self.no_subprocess.call_args.kwargs["env"]
        for key in ("PGPASSWORD", "PGHOST", "PGSERVICE", "DATABASE_URL"):
            self.assertNotIn(key, env)
        self.assertFalse(self.no_subprocess.call_args.kwargs["check"])

    def test_create_is_fresh_scram_and_exports_passwordless_url(self):
        seen = []

        def fake_command(tool, args, **kwargs):
            seen.append((tool, args))
            if tool == "initdb":
                data = Path(args[args.index("-D") + 1])
                data.mkdir(mode=0o700)
                pg.private_file(data / "postgresql.conf", "# initdb\n")
            return subprocess.CompletedProcess([], 0, "", "")

        with patch.object(pg, "require_runtime", return_value=self.temp), \
                patch.object(pg, "verify_binaries", return_value={x: "16.15" for x in pg.TOOLS}), \
                patch.object(pg, "free_port", return_value=54321), \
                patch.object(pg, "command", side_effect=fake_command), \
                patch.object(pg, "start_server"), patch.object(pg, "sql"), \
                patch.object(pg, "probe", return_value=160015), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            pg.create(self.state_path, self.env_file)
            state = pg.load_state(self.state_path)
            root = Path(state["root"])
            password = (root / "pgpass").read_text().strip().split(":")[-1]
            self.assertEqual(output.getvalue(), "")
            self.assertNotIn(password, output.getvalue())
            self.assertFalse((root / "init-password").exists())
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((root / "socket").stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((root / "pgpass").stat().st_mode), 0o600)
            exports = self.env_file.read_text()
            self.assertIn("postgresql+psycopg2://reqsys_app@127.0.0.1:54321/reqsys_test", exports)
            self.assertNotIn(password, exports)
            self.assertNotIn(password, pg.receipt_path().read_text())
            self.assertIn("--auth-host=scram-sha-256", seen[0][1])
            self.assertIn("--auth-local=scram-sha-256", seen[0][1])
            self.assertNotIn("trust", (root / "data" / "pg_hba.conf").read_text())
            with self.assertRaisesRegex(pg.FixtureError, "state_already_exists"):
                pg.create(self.state_path, self.env_file)

    def test_failed_init_removes_password_and_owned_tree(self):
        with patch.object(pg, "require_runtime", return_value=self.temp), \
                patch.object(pg, "verify_binaries", return_value={x: "16.15" for x in pg.TOOLS}), \
                patch.object(pg, "free_port", return_value=54321), \
                patch.object(pg, "command", side_effect=pg.FixtureError("initdb_failed_exit_1")), \
                patch.object(pg, "is_ready", return_value=2), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaisesRegex(pg.FixtureError, "initdb_failed_exit_1"):
                pg.create(self.state_path, self.env_file)
        self.assertEqual(output.getvalue(), "")
        self.assertFalse(self.state_path.exists())
        self.assertEqual(list(self.temp.glob("reqsys-pg16-*")), [])

    def test_cleanup_is_idempotent_and_never_touches_other_cluster(self):
        state = self.make_state()
        unrelated = self.temp / "preexisting-postgres"
        unrelated.mkdir()
        sentinel = unrelated / "keep"
        sentinel.write_text("unchanged")
        with patch.object(pg, "require_runtime", return_value=self.temp), \
                patch.object(pg, "is_ready", return_value=2):
            pg.cleanup(self.state_path)
            pg.cleanup(self.state_path)
        self.assertFalse(Path(state["root"]).exists())
        self.assertFalse(self.env_file.exists())
        self.assertEqual(sentinel.read_text(), "unchanged")
        self.no_subprocess.assert_not_called()

    def test_cleanup_failure_preserves_state_for_always_retry(self):
        state = self.make_state()
        with patch.object(pg, "require_runtime", return_value=self.temp), \
                patch.object(pg, "stop_server", side_effect=pg.FixtureError("stop_failed")):
            with self.assertRaisesRegex(pg.FixtureError, "stop_failed"):
                pg.cleanup(self.state_path)
        self.assertTrue(self.state_path.exists())
        self.assertTrue(Path(state["root"]).exists())
        self.assertEqual(json.loads(pg.receipt_path().read_text())["cleanup"], "blocked")

    def test_cleanup_requires_no_listener_before_deleting_owned_data(self):
        state = self.make_state()
        with patch.object(pg, "require_runtime", return_value=self.temp), \
                patch.object(pg, "stop_server"), patch.object(pg, "is_ready", return_value=0):
            with self.assertRaisesRegex(pg.FixtureError, "cleanup_listener_not_absent"):
                pg.cleanup(self.state_path)
        self.assertTrue(Path(state["root"]).exists())
        self.assertTrue(self.state_path.exists())
        self.assertEqual(json.loads(pg.receipt_path().read_text())["cleanup"], "blocked")

    def test_wrong_password_requires_real_authentication_rejection(self):
        state = self.make_state()
        bad = Path(state["root"]) / "wrong-pgpass"
        with patch.object(pg, "sql", return_value=subprocess.CompletedProcess(
                [], 2, "", "FATAL: password authentication failed for user reqsys_app")) as sql:
            pg.reject_wrong_password(state)
        self.assertEqual(sql.call_args.kwargs["passfile"], bad)
        self.assertFalse(bad.exists())
        for code, error in ((0, ""), (2, "connection refused")):
            with patch.object(pg, "sql", return_value=subprocess.CompletedProcess([], code, "", error)):
                with self.assertRaisesRegex(pg.FixtureError, "wrong_password_negative_failed"):
                    pg.reject_wrong_password(state)
            self.assertFalse(bad.exists())

    def test_stop_refuses_foreign_postmaster_datadir(self):
        state = self.make_state()
        pg.private_file(Path(state["root"]) / "data" / "postmaster.pid",
                        "123\n/var/lib/postgresql/16/main\n0\n54321\n")
        with patch.object(pg, "command") as command:
            with self.assertRaisesRegex(pg.FixtureError, "postmaster_identity_mismatch"):
                pg.stop_server(state)
            command.assert_not_called()

    def test_exercise_requires_stopped_database_connection_failure(self):
        state = self.make_state()
        marker = "c" * 32
        with patch.object(pg.secrets, "token_hex", return_value=marker), \
                patch.object(pg, "reject_wrong_password"), \
                patch.object(pg, "probe", return_value=160015), \
                patch.object(pg, "stop_server"), patch.object(pg, "start_server") as start, \
                patch.object(pg, "is_ready", return_value=0), \
                patch.object(pg, "sql", return_value=subprocess.CompletedProcess([], 0, marker, "")):
            with self.assertRaisesRegex(pg.FixtureError, "stopped_database_negative_failed"):
                pg.exercise(state)
            start.assert_not_called()

    def test_exercise_records_positive_negative_and_restart(self):
        state = self.make_state()
        marker = "c" * 32
        outcomes = [subprocess.CompletedProcess([], code, value, "") for code, value in
                    [(0, ""), (0, ""), (0, marker), (2, ""), (0, marker), (0, "")]]
        with patch.object(pg.secrets, "token_hex", return_value=marker), \
                patch.object(pg, "reject_wrong_password"), \
                patch.object(pg, "probe", side_effect=[160015, pg.FixtureError("postgres_not_ready"), 160015]), \
                patch.object(pg, "stop_server"), patch.object(pg, "start_server"), \
                patch.object(pg, "is_ready", return_value=2), \
                patch.object(pg, "sql", side_effect=outcomes):
            pg.exercise(state)
        evidence = json.loads(pg.receipt_path().read_text())
        self.assertTrue(evidence["independent_read"])
        self.assertTrue(evidence["stopped_probe_rejected"])
        self.assertTrue(evidence["restart_persistence"])
        self.assertEqual(evidence["stopped_psql_exit"], 2)
        self.assertNotIn(marker, json.dumps(evidence))


if __name__ == "__main__":
    unittest.main()
