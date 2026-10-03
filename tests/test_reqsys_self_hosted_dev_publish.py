"""Gates que impedem ativação vazia, stale ou em host incorreto."""
from datetime import datetime, timedelta, timezone
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/reqsys_self_hosted_dev_publish.py"
spec = importlib.util.spec_from_file_location("selfhost_publish", SCRIPT)
publish = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publish)


class FakePrivateFiles:
    def directory(self, path):
        path.mkdir(exist_ok=True)

    def check(self, path):
        if not path.exists():
            raise FileNotFoundError(path)

    def create(self, path, content):
        with path.open("xb") as stream:
            stream.write(content)


class PublishTests(unittest.TestCase):
    def proof(self):
        proof = {
            "schema_version": "1",
            "status": "verified",
            "host": publish.HOST,
            "project": publish.PROJECT,
            "target_sha": "a" * 40,
            "source_sha256": "b" * 64,
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "sqlite_integrity_ok": True,
            "target_verified": True,
            "source_rows": 3,
            "copied_rows": 3,
            "table_counts": {"requisitos": 3},
            "database_identity": {
                "database": "reqsys",
                "container_id": "c" * 64,
                "postgres_system_identifier": "123456789",
            },
        }
        proof["proof_integrity_sha256"] = publish.proof_integrity(proof)
        return proof

    def validate(self, proof):
        return publish.validate_restore_proof(
            proof, "a" * 40, "b" * 64, datetime.now(timezone.utc)
        )

    def test_other_host_blocked(self):
        with patch.object(publish.socket, "gethostname", return_value="NOTERI"):
            with self.assertRaises(publish.PublishError):
                publish.require_host()

    def test_secret_retry_preserves_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "secrets"
            private = FakePrivateFiles()
            self.assertEqual(len(publish.initialize_secrets(root, private)), 3)
            original = {p.name: p.read_bytes() for p in root.iterdir()}
            self.assertEqual(publish.initialize_secrets(root, private), [])
            self.assertEqual(original, {p.name: p.read_bytes() for p in root.iterdir()})

    def test_invalid_existing_secret_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "secrets"
            root.mkdir()
            path = root / "db_owner_password"
            path.write_bytes(b"old-invalid-value\n")
            with self.assertRaises(publish.PublishError):
                publish.initialize_secrets(root, FakePrivateFiles())
            self.assertEqual(path.read_bytes(), b"old-invalid-value\n")

    def test_configuration_preserves_exact_existing_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "runtime.env"
            path.write_bytes(b"old\n")
            private = FakePrivateFiles()
            publish.WindowsPrivateFiles.preserving(private, path, b"old\n")
            with self.assertRaises(publish.PublishError):
                publish.WindowsPrivateFiles.preserving(private, path, b"new\n")
            self.assertEqual(path.read_bytes(), b"old\n")

    def test_config_is_private_local_dev(self):
        config = publish.render_config(Path("C:/Private/secrets"), ("", "")).decode()
        self.assertIn('SITE_ADDRESS=":80"', config)
        self.assertIn('BIND_ADDRESS="127.0.0.1"', config)
        self.assertIn('APP_ENV="development"', config)
        self.assertNotIn("password=", config)
        self.assertNotIn("jwt_secret=", config)

    def configured_publisher(self, root):
        publisher = object.__new__(publish.Publisher)
        publisher.root = root
        publisher.env_file = root / "runtime.env"
        publisher.override = root / "compose.override.json"
        publisher.expected = "a" * 40
        private = FakePrivateFiles()
        private.preserving = lambda path, content: publish.WindowsPrivateFiles.preserving(
            private, path, content
        )
        publisher.private = private
        publisher.compose_calls = []
        publisher.compose = lambda *args: publisher.compose_calls.append(args)
        return publisher

    def test_pages_api_origin_separated_from_local_ingress_and_jwt_audience(self):
        with tempfile.TemporaryDirectory() as temporary:
            publisher = self.configured_publisher(Path(temporary) / "ReqSys/SelfHostedDev")
            ids = ("11111111-1111-1111-1111-111111111111",
                   "22222222-2222-2222-2222-222222222222")
            with patch.object(publish, "discover_public_ids", return_value=ids):
                self.assertEqual(publisher.configure(), ids)
            override = publish.json.loads(publisher.override.read_bytes())
            env = override["services"]["api"]["environment"]
            self.assertEqual(env["APP_PUBLIC_URL"],
                             "https://ericson-j-santos.github.io/reqsys-v2-enterprise-real/dev")
            self.assertEqual(env["CORS_ORIGINS"].split(","), [
                "https://ericson-j-santos.github.io", "http://localhost:18080",
            ])
            self.assertNotIn("/dev", env["CORS_ORIGINS"])
            self.assertNotIn("*", env["CORS_ORIGINS"])
            self.assertEqual(env["JWT_AUDIENCE"], "http://localhost:18080")
            self.assertEqual(env["REQSYS_BUILD_SHA"], publisher.expected)
            runtime = dict(
                (key, publish.json.loads(value)) for key, value in
                (line.split("=", 1) for line in publisher.env_file.read_text().splitlines())
            )
            self.assertEqual(runtime["PUBLIC_ORIGIN"], "http://localhost:18080")
            self.assertEqual(runtime["BIND_ADDRESS"], "127.0.0.1")
            self.assertEqual((runtime["HTTP_PORT"], runtime["HTTPS_PORT"]), ("18080", "18443"))
            self.assertEqual(runtime["SITE_ADDRESS"], ":80")
            self.assertNotIn("API_PUBLIC_URL", env)
            self.assertEqual(set(override["services"]["frontend"]), {"labels"})
            self.assertTrue(all("password" not in key.lower() and "secret" not in key.lower()
                                for key in env))
            self.assertEqual(publisher.compose_calls, [("config", "--quiet")])

    def test_existing_private_override_never_rewritten_for_pages_config(self):
        with tempfile.TemporaryDirectory() as temporary:
            publisher = self.configured_publisher(Path(temporary) / "ReqSys/SelfHostedDev")
            publisher.root.mkdir(parents=True)
            old_override = b'{"services":{"api":{"environment":{"CORS_ORIGINS":"old"}}}}\n'
            publisher.override.write_bytes(old_override)
            with patch.object(publish, "discover_public_ids", return_value=("", "")):
                with self.assertRaisesRegex(publish.PublishError, "existing_configuration_mismatch"):
                    publisher.configure()
            self.assertEqual(publisher.override.read_bytes(), old_override)
            self.assertEqual(publisher.compose_calls, [])

    def test_fresh_complete_proof_accepted(self):
        self.assertEqual(self.validate(self.proof()), {"requisitos": 3})

    def test_stale_future_empty_wrong_target_and_unbound_backup_rejected(self):
        for field, value in (
            ("verified_at", (datetime.now(timezone.utc) -
                             timedelta(hours=2)).isoformat()),
            ("verified_at", (datetime.now(timezone.utc) +
                             timedelta(hours=2)).isoformat()),
            ("copied_rows", 0),
            ("target_sha", "d" * 40),
            ("source_sha256", "d" * 64),
            ("host", "NOTERI"),
            ("target_verified", False),
            ("table_counts", {"requisitos": 2}),
            ("table_counts", {'bad"; DROP TABLE x': 3}),
        ):
            with self.subTest(field=field, value=value):
                proof = self.proof()
                proof[field] = value
                with self.assertRaises(publish.PublishError):
                    self.validate(proof)


    def raw_proof(self):
        proof = self.proof()
        proof.update({
            "schema_version": "1.0.0",
            "contract": "reqsys-sqlite-postgres-import",
            "digests_match": True,
            "independent_readback": True,
            "migration_committed": True,
        })
        return proof

    def test_raw_import_evidence_requires_committed_independent_readback(self):
        raw = self.raw_proof()
        proof = publish.aggregate_restore_proof(
            raw, "a" * 40, "b" * 64, self.proof()["database_identity"],
            datetime.now(timezone.utc)
        )
        self.assertEqual(self.validate(proof), {"requisitos": 3})
        for field in ("digests_match", "independent_readback", "migration_committed"):
            with self.subTest(field=field):
                bad = dict(raw)
                bad[field] = False
                with self.assertRaises(publish.PublishError):
                    publish.aggregate_restore_proof(
                        bad, "a" * 40, "b" * 64,
                        self.proof()["database_identity"],
                        datetime.now(timezone.utc)
                    )

    def test_valid_metadata_cannot_change_without_integrity_update(self):
        proof = self.proof()
        proof["database_identity"]["container_id"] = "d" * 64
        with self.assertRaisesRegex(publish.PublishError, "integrity_mismatch"):
            self.validate(proof)

    def test_copied_row_boolean_is_not_accepted_as_integer(self):
        proof = self.proof()
        proof.update(source_rows=1, copied_rows=True, table_counts={"requisitos": 1})
        proof["proof_integrity_sha256"] = publish.proof_integrity(proof)
        with self.assertRaisesRegex(publish.PublishError, "empty_or_incomplete"):
            self.validate(proof)

    def test_live_restore_rejects_replaced_database_and_wrong_counts(self):
        publisher = object.__new__(publish.Publisher)
        proof = self.proof()
        with patch.object(publisher, "compose", return_value="c" * 64):
            with patch.object(publisher, "run", return_value="d" * 64):
                with self.assertRaisesRegex(publish.PublishError, "container_changed"):
                    publisher.verify_live_restore(proof, {"requisitos": 3})
        with patch.object(publisher, "compose", side_effect=[
            "c" * 64, "identity|123456789\nrequisitos|2"
        ]):
            with patch.object(publisher, "run", return_value="c" * 64):
                with self.assertRaisesRegex(publish.PublishError, "counts_mismatch"):
                    publisher.verify_live_restore(proof, {"requisitos": 3})

    def test_bounded_evidence_rejects_old_oversized_or_non_object_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "evidence.json"
            path.write_bytes(b"x" * 262145)
            with self.assertRaisesRegex(publish.PublishError, "too_large"):
                publish.bounded_json(path, FakePrivateFiles())
            path.write_bytes(b"[]")
            with self.assertRaisesRegex(publish.PublishError, "not_object"):
                publish.bounded_json(path, FakePrivateFiles())


    def test_cleanup_cannot_remove_unowned_or_other_container(self):
        publisher = object.__new__(publish.Publisher)
        publisher.source = Path.cwd()
        publisher.events = []
        attempt = "a" * 24
        with patch.object(publish.subprocess, "run") as run:
            with self.assertRaisesRegex(publish.PublishError, "identity_invalid"):
                publisher.cleanup_importer("reqsys-live-api-1", attempt)
            run.assert_not_called()
        response = SimpleNamespace(returncode=0, stdout="{}", stderr="")
        with patch.object(publish.subprocess, "run", return_value=response) as run:
            with self.assertRaisesRegex(publish.PublishError, "owner_mismatch"):
                publisher.cleanup_importer("reqsys-dev-restore-" + attempt, attempt)
            self.assertEqual(run.call_count, 1)

    def test_cleanup_removes_exact_owned_ephemeral_container_without_volumes(self):
        publisher = object.__new__(publish.Publisher)
        publisher.source = Path.cwd()
        publisher.events = []
        attempt = "a" * 24
        name = "reqsys-dev-restore-" + attempt
        labels = {
            "com.docker.compose.project": publish.PROJECT,
            "com.docker.compose.service": "api",
            "io.reqsys.selfhost.instance": publish.INSTANCE,
            "io.reqsys.selfhost.restore_attempt": attempt,
        }
        inspected = SimpleNamespace(returncode=0, stdout=publish.json.dumps(labels), stderr="")
        removed = SimpleNamespace(returncode=0, stdout=name, stderr="")
        with patch.object(publish.subprocess, "run", side_effect=[inspected, removed]) as run:
            publisher.cleanup_importer(name, attempt)
            self.assertEqual(run.call_args.args[0], ["docker", "rm", "--force", name])
            self.assertFalse(run.call_args.kwargs["shell"])

    @unittest.skipUnless(os.name == "nt", "DACL Windows")
    def test_actual_windows_private_acl_roundtrip(self):
        with tempfile.TemporaryDirectory() as temporary:
            private = publish.WindowsPrivateFiles()
            root = Path(temporary) / "private"
            private.directory(root)
            private.create(root / "sample", b"sample\n")
            private.check(root)
            private.check(root / "sample")

    @unittest.skipUnless(os.name == "nt", "DACL Windows")
    def test_actual_windows_extra_admin_grant_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            private = publish.WindowsPrivateFiles()
            root = Path(temporary) / "private"
            private.directory(root)
            descriptor = publish.ctypes.c_void_p()
            sddl = private.directory_sddl + "(A;OICI;FA;;;BA)"
            self.assertTrue(
                private.adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(
                    sddl, 1, publish.ctypes.byref(descriptor), None
                ), "test_descriptor_conversion_failed"
            )
            try:
                self.assertTrue(
                    private.adv.SetFileSecurityW(str(root), 0x80000004, descriptor),
                    "test_descriptor_update_failed"
                )
            finally:
                private.kernel.LocalFree(descriptor)
            try:
                with self.assertRaisesRegex(publish.PublishError, "not_exclusive"):
                    private.check(root)
            finally:
                private.secure(root)

    @unittest.skipUnless(os.name == "nt", "DACL Windows")
    def test_actual_windows_transport_and_publisher_acl_interoperate(self):
        try:
            import win32security  # noqa: F401
        except ImportError:
            self.fail("Windows ACL interoperation test requires pywin32")
        path = SCRIPT.parent / "dev_backup_transport.py"
        crypto_spec = importlib.util.spec_from_file_location("backup_transport_acl", path)
        crypto = importlib.util.module_from_spec(crypto_spec)
        crypto_spec.loader.exec_module(crypto)
        with tempfile.TemporaryDirectory() as temporary:
            private = publish.WindowsPrivateFiles()
            root = Path(temporary) / "private"
            root.mkdir()
            crypto.secure_acl(root, directory=True)
            private.check(root)
            file = root / "private-metadata"
            file.write_bytes(b"private-metadata\n")
            crypto.secure_acl(file, directory=False)
            private.check(file)

    @unittest.skipUnless(os.name == "nt", "DACL Windows")
    def test_actual_windows_alias_sid_normalization(self):
        private = publish.WindowsPrivateFiles()
        self.assertTrue(
            private._canonical_sid("SY") == private._canonical_sid("S-1-5-18"),
            "system_sid_alias_not_normalized"
        )



if __name__ == "__main__":
    unittest.main()
