"""Meaningful rejection tests for the bounded DEV ciphertext handoff."""
import hashlib
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric import rsa
from scripts import dev_backup_transport as transport


class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        connection = sqlite3.connect(":memory:")
        for index in range(11):
            connection.execute(f"CREATE TABLE t{index} (id INTEGER PRIMARY KEY)")
            connection.executemany(f"INSERT INTO t{index} VALUES (?)",
                                   [(n,) for n in range(20 if index == 0 else 19)])
        cls.sqlite = connection.serialize()
        connection.close()
        cls.sqlite_sha = hashlib.sha256(cls.sqlite).hexdigest()
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        cls.other_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)

    def setUp(self):
        self.sha_patch = patch.object(transport, "SQLITE_SHA256", self.sqlite_sha)
        self.size_patch = patch.object(transport, "SQLITE_BYTES", len(self.sqlite))
        self.sha_patch.start()
        self.size_patch.start()
        self.addCleanup(self.sha_patch.stop)
        self.addCleanup(self.size_patch.stop)
        self.envelope = transport.seal_sqlite(
            self.sqlite, self.key.public_key(), 12345, "a" * 40, now=1000)

    def open(self, envelope=None, *, key=None, now=1100, run=12345, sha="a" * 40):
        envelope = self.envelope if envelope is None else envelope
        return transport.open_sqlite(
            envelope, self.key if key is None else key, expected_run_id=run,
            expected_source_sha=sha, expected_envelope_sha256=transport.digest(envelope),
            now=now)

    def test_roundtrip_preserves_bytes_and_counts(self):
        plaintext, report = self.open()
        self.assertEqual(plaintext, self.sqlite)
        self.assertEqual((report["tables"], report["rows"]), (11, 210))
        self.assertNotIn(self.sqlite[:64], self.envelope)

    def test_ciphertext_tampering_fails_authenticated_decryption(self):
        value = json.loads(self.envelope)
        raw = bytearray(transport.unb64(value["ciphertext_b64"], len(self.sqlite) + 16))
        raw[5] ^= 1
        value["ciphertext_b64"] = transport.b64(bytes(raw))
        with self.assertRaisesRegex(transport.TransportError, "envelope_authentication_failed"):
            self.open(transport.canonical(value))

    def test_bound_host_or_snapshot_cannot_change(self):
        for field in ("target_host", "source_host", "snapshot_id"):
            value = json.loads(self.envelope)
            value["header"][field] = "changed"
            with self.assertRaisesRegex(transport.TransportError, "binding_mismatch"):
                self.open(transport.canonical(value))

    def test_exact_artifact_run_commit_and_recipient_required(self):
        for kwargs in ({"run": 12346}, {"sha": "b" * 40}, {"key": self.other_key}):
            with self.assertRaisesRegex(transport.TransportError, "binding_mismatch"):
                self.open(**kwargs)

    def test_expired_or_future_envelope_rejected(self):
        for now in (4600, 699):
            with self.assertRaisesRegex(transport.TransportError, "expired_or_future"):
                self.open(now=now)

    def test_download_digest_mismatch_rejected_before_open(self):
        with self.assertRaisesRegex(transport.TransportError, "artifact_digest_mismatch"):
            transport.open_sqlite(self.envelope, self.key, expected_run_id=12345,
                expected_source_sha="a" * 40, expected_envelope_sha256="0" * 64, now=1100)

    def test_fixed_sqlite_digest_is_mandatory(self):
        with self.assertRaisesRegex(transport.TransportError, "fixed_backup_digest_mismatch"):
            transport.seal_sqlite(b"bad", self.key.public_key(), 12345, "a" * 40, now=1000)

    def test_recipient_config_requires_pinned_key(self):
        der = transport.public_der(self.key.public_key())
        cfg = {"schema": transport.SCHEMA, "target_host": transport.TARGET_HOST,
               "public_key_der_b64": transport.b64(der),
               "recipient_sha256": transport.digest(der)}
        self.assertEqual(transport.reviewed_recipient(cfg, transport.digest(der)).key_size, 3072)
        with self.assertRaisesRegex(transport.TransportError, "not_pinned"):
            transport.reviewed_recipient(cfg, "0" * 64)

    def test_extra_fields_and_boolean_run_are_rejected(self):
        value = json.loads(self.envelope)
        value["untrusted"] = "data"
        with self.assertRaisesRegex(transport.TransportError, "invalid_envelope_schema"):
            self.open(transport.canonical(value))
        with self.assertRaisesRegex(transport.TransportError, "invalid_source_run_id"):
            transport.seal_sqlite(self.sqlite, self.key.public_key(), True, "a" * 40, now=1000)


class ResticProvisionTests(unittest.TestCase):
    def package(self, filename=None, extra=None):
        import io
        import zipfile
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(filename or transport.RESTIC_ZIP_MEMBER, b"MZfixture-executable")
            if extra:
                archive.writestr(extra, b"must-not-extract")
        return buffer.getvalue()

    def verified_exe(self, package):
        with patch.object(transport, "RESTIC_ZIP_BYTES", len(package)), \
                patch.object(transport, "RESTIC_ZIP_SHA256", transport.digest(package)):
            return transport.restic_exe_from_verified_zip(package)

    def test_exact_zip_member_only_ignores_other_paths(self):
        package = self.package(extra="../../outside.exe")
        self.assertEqual(self.verified_exe(package), b"MZfixture-executable")

    def test_package_checksum_and_required_member_fail_closed(self):
        with self.assertRaisesRegex(transport.TransportError, "package_checksum"):
            transport.restic_exe_from_verified_zip(b"untrusted")
        with self.assertRaisesRegex(transport.TransportError, "member_missing"):
            self.verified_exe(self.package(filename="../restic_0.18.0_windows_amd64.exe"))

    def test_restic_snapshot_header_and_file_metadata(self):
        data = b"\n".join([
            transport.canonical({"struct_type": "snapshot", "id": transport.SNAPSHOT_ID}),
            transport.canonical({"struct_type": "node", "type": "dir", "path": "/private"}),
            transport.canonical({"struct_type": "node", "type": "file",
                                 "path": "/private/reqsys-dev.sqlite", "size": transport.SQLITE_BYTES}),
        ])
        files = transport.parse_snapshot_inventory(data)
        self.assertEqual(files, [{"snapshot_path": "/private/reqsys-dev.sqlite",
                                  "bytes": transport.SQLITE_BYTES}])
        self.assertEqual(transport.selected_sqlite_path(files), "/private/reqsys-dev.sqlite")

    def test_other_snapshot_traversal_and_ambiguous_db_rejected(self):
        with self.assertRaisesRegex(transport.TransportError, "identity_mismatch"):
            transport.parse_snapshot_inventory(transport.canonical(
                {"struct_type": "snapshot", "id": "0" * 64}))
        with self.assertRaisesRegex(transport.TransportError, "path_invalid"):
            transport.safe_snapshot_path("/private/../other.db")
        with self.assertRaisesRegex(transport.TransportError, "ambiguous"):
            transport.selected_sqlite_path([
                {"snapshot_path": "/one.db", "bytes": transport.SQLITE_BYTES},
                {"snapshot_path": "/two.db", "bytes": transport.SQLITE_BYTES}])

    def test_header_required_and_negative_sizes_rejected(self):
        with self.assertRaisesRegex(transport.TransportError, "header_missing"):
            transport.parse_snapshot_inventory(b"")
        data = b"\n".join([
            transport.canonical({"struct_type": "snapshot", "id": transport.SNAPSHOT_ID}),
            transport.canonical({"struct_type": "node", "type": "file", "path": "/one.db",
                                 "size": -1}),
        ])
        with self.assertRaisesRegex(transport.TransportError, "size_invalid"):
            transport.parse_snapshot_inventory(data)


class DependencyCorrelationTests(unittest.TestCase):
    def test_fixed_migration_and_portable_site_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            migration = base / "reqsys-migration-python-12345"
            migration.mkdir()
            portable = base / "reqsys-python-3.12.10-job_name-12345-1" / "Lib" / "site-packages"
            portable.mkdir(parents=True)
            environment = {"RUNNER_TEMP": str(base), "GITHUB_RUN_ID": "12345",
                           "GITHUB_JOB": "job_name", "GITHUB_RUN_ATTEMPT": "1",
                           "REQSYS_MIGRATION_DEPENDENCIES": str(migration), "REQSYS_PYTHON_SITE": ""}
            with patch.dict(os.environ, environment):
                self.assertEqual(transport.migration_dependency_site(), migration)
            environment.update(REQSYS_MIGRATION_DEPENDENCIES="", REQSYS_PYTHON_SITE=str(portable))
            with patch.dict(os.environ, environment):
                self.assertEqual(transport.migration_dependency_site(), portable)

    @unittest.skipUnless(os.name == "nt", "Windows DLL search API")
    def test_dll_search_handles_are_retained_without_processing_pth(self):
        import sys
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            site = base / "reqsys-migration-python-12345"
            for relative in ("win32/lib", "pywin32_system32"):
                (site / relative).mkdir(parents=True)
            environment = {"RUNNER_TEMP": str(base), "GITHUB_RUN_ID": "12345",
                           "REQSYS_MIGRATION_DEPENDENCIES": str(site), "REQSYS_PYTHON_SITE": ""}
            with patch.dict(os.environ, environment), \
                    patch.dict(transport._WINDOWS_DLL_HANDLES, {}, clear=True), \
                    patch.object(sys, "path", list(sys.path)), \
                    patch.object(os, "add_dll_directory", return_value=object()) as add_dll:
                transport.initialize_windows_libraries()
                transport.initialize_windows_libraries()
                add_dll.assert_called_once_with(str(site / "pywin32_system32"))
                self.assertEqual(sys.path[:3], [str(site), str(site / "win32"), str(site / "win32/lib")])
                self.assertIn(str(site / "pywin32_system32"), transport._WINDOWS_DLL_HANDLES)

    def test_other_run_or_outside_temp_site_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            stale = base / "reqsys-migration-python-12344"
            stale.mkdir()
            with patch.dict(os.environ, {"RUNNER_TEMP": str(base), "GITHUB_RUN_ID": "12345",
                    "REQSYS_MIGRATION_DEPENDENCIES": str(stale), "REQSYS_PYTHON_SITE": ""}):
                with self.assertRaisesRegex(transport.TransportError, "path_not_fixed"):
                    transport.migration_dependency_site()


@unittest.skipUnless(os.name == "nt", "real Windows DPAPI and DACL")
class WindowsIdentityTests(unittest.TestCase):
    def test_real_dpapi_identity_replay_and_ciphertext_restore(self):
        import win32security
        from scripts import reqsys_self_hosted_dev_publish as publisher

        connection = sqlite3.connect(":memory:")
        for index in range(11):
            connection.execute(f"CREATE TABLE t{index} (id INTEGER PRIMARY KEY)")
            connection.executemany(f"INSERT INTO t{index} VALUES (?)",
                                   [(number,) for number in range(20 if index == 0 else 19)])
        data = connection.serialize()
        connection.close()
        with tempfile.TemporaryDirectory() as temporary:
            shared = Path(temporary) / "ReqSys"
            shared.mkdir()
            before = win32security.ConvertSecurityDescriptorToStringSecurityDescriptor(
                win32security.GetFileSecurity(str(shared), win32security.DACL_SECURITY_INFORMATION),
                1, win32security.DACL_SECURITY_INFORMATION)
            environment = {"LOCALAPPDATA": temporary, "REQSYS_MIGRATION_DEPENDENCIES": "",
                           "REQSYS_PYTHON_SITE": ""}
            with patch.dict(os.environ, environment), \
                    patch.object(transport.socket, "gethostname", return_value=transport.TARGET_HOST), \
                    patch.object(transport, "SQLITE_SHA256", transport.digest(data)), \
                    patch.object(transport, "SQLITE_BYTES", len(data)):
                key, first_public = transport.receiver_identity()
                replay_key, second_public = transport.receiver_identity()
                self.assertEqual(first_public, second_public)
                self.assertEqual(transport.public_der(key.public_key()),
                                 transport.public_der(replay_key.public_key()))
                root = transport.receiver_root()
                self.assertTrue((root / "receiver-private-key.dpapi").is_file())
                envelope = transport.seal_sqlite(data, key.public_key(), 12345, "a" * 40)
                report = transport.restore_on_receiver(envelope, expected_run_id=12345,
                    expected_source_sha="a" * 40, expected_envelope_sha256=transport.digest(envelope))
                self.assertTrue(report["ok"])
                self.assertEqual((root / "restored-dev.sqlite").read_bytes(), data)
                # Cross-check the publisher's independent WinAPI ACL reader.
                independent = publisher.WindowsPrivateFiles()
                for path in (root.parent, root, root / "receiver-private-key.dpapi",
                             root / "receiver-public-key.json", root / "restored-dev.sqlite"):
                    independent.check(path)
                after = win32security.ConvertSecurityDescriptorToStringSecurityDescriptor(
                    win32security.GetFileSecurity(str(shared), win32security.DACL_SECURITY_INFORMATION),
                    1, win32security.DACL_SECURITY_INFORMATION)
                self.assertEqual(before, after)

    def test_actual_acl_is_protected_and_exact_for_directory_and_file(self):
        import win32security
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "private"
            folder.mkdir()
            sample = folder / "sample"
            sample.write_bytes(b"public test fixture")
            for path, directory in ((folder, True), (sample, False)):
                transport.secure_acl(path, directory=directory)
                descriptor = win32security.GetFileSecurity(str(path),
                    win32security.DACL_SECURITY_INFORMATION)
                self.assertTrue(descriptor.GetSecurityDescriptorControl()[0] & 0x1000,
                                "the DACL must disable inherited access")
                acl = descriptor.GetSecurityDescriptorDacl()
                self.assertEqual(acl.GetAceCount(), 2)
                for index in range(acl.GetAceCount()):
                    ace = acl.GetAce(index)
                    self.assertEqual(ace[0], (win32security.ACCESS_ALLOWED_ACE_TYPE, 3 if directory else 0))
                    self.assertEqual(ace[1], 0x1F01FF)

    def test_existing_protected_folder_with_untrusted_sid_is_rejected(self):
        import win32security
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "private"
            transport.private_scope_directory(folder)
            descriptor = win32security.GetFileSecurity(str(folder), win32security.DACL_SECURITY_INFORMATION)
            acl = descriptor.GetSecurityDescriptorDacl()
            everyone = win32security.CreateWellKnownSid(win32security.WinWorldSid, None)
            acl.AddAccessAllowedAceEx(win32security.ACL_REVISION, 0, 0x1F01FF, everyone)
            descriptor.SetSecurityDescriptorDacl(1, acl, 0)
            win32security.SetFileSecurity(str(folder),
                win32security.DACL_SECURITY_INFORMATION | win32security.PROTECTED_DACL_SECURITY_INFORMATION,
                descriptor)
            with self.assertRaisesRegex(transport.TransportError, "acl_untrusted"):
                transport.private_scope_directory(folder)


if __name__ == "__main__":
    unittest.main()
