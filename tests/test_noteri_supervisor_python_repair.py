"""Testes de reparo reversivel sem iniciar supervisor ou alterar o perfil."""
from __future__ import annotations
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock
from scripts import noteri_supervisor_python_repair as m


class RepairTests(unittest.TestCase):
    def fixture(self, base):
        wrapper, bundle, records, config = base / "startup.cmd", base / "python", base / "records", base / "service.json"
        original = (f'@echo off\r\nsetlocal\r\ncd /d "{base}"\r\n:restart\r\n'
                    f'"{base / "old" / "python.exe"}" -m scripts.service_supervisor --config "{config}"\r\n'
                    'timeout /t 5 /nobreak >nul\r\ngoto restart\r\n').encode()
        wrapper.write_bytes(original)
        return wrapper, bundle, records, config, original

    def apply(self, f, **kwargs):
        wrapper, bundle, records, config, original = f
        return m.repair_reference(wrapper, bundle, records, config, m.digest(original),
                                  prepare=kwargs.get("prepare", lambda _: None),
                                  validate=kwargs.get("validate", lambda _: None))

    def test_apply_preserves_wrapper_and_saves_exact_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            f = self.fixture(Path(temp))
            result = self.apply(f)
            expected = f[4].replace(str(Path(temp) / "old" / "python.exe").encode(), str(f[1] / "python.exe").encode())
            self.assertEqual(f[0].read_bytes(), expected)
            self.assertEqual((f[2] / "startup.original.cmd").read_bytes(), f[4])
            self.assertEqual(result["state"], "reference_repaired")
            self.assertFalse(m.obj(f[2] / "receipt.json")["process_started"])

    def test_replay_does_not_repeat_preparation_or_modify_files(self):
        with tempfile.TemporaryDirectory() as temp:
            f = self.fixture(Path(temp))
            self.apply(f)
            before = {str(p): p.read_bytes() for p in Path(temp).rglob("*") if p.is_file()}
            result = self.apply(f, prepare=lambda _: self.fail("duplicate installation"))
            self.assertEqual(result["state"], "already_applied")
            self.assertEqual(before, {str(p): p.read_bytes() for p in Path(temp).rglob("*") if p.is_file()})

    def test_wrong_digest_does_not_mutate(self):
        with tempfile.TemporaryDirectory() as temp:
            f = self.fixture(Path(temp))
            with self.assertRaisesRegex(m.Blocked, "lease_mismatch"):
                m.repair_reference(*f[:4], "0" * 64,
                                   prepare=lambda _: self.fail("network"), validate=lambda _: None)
            self.assertEqual(f[0].read_bytes(), f[4])
            self.assertFalse(f[2].exists())

    def test_validation_failure_preserves_original_startup(self):
        with tempfile.TemporaryDirectory() as temp:
            f = self.fixture(Path(temp))
            def fail(_):
                raise m.Blocked("invalid_python")
            with self.assertRaisesRegex(m.Blocked, "invalid_python"):
                self.apply(f, validate=fail)
            self.assertEqual(f[0].read_bytes(), f[4])
            self.assertFalse(f[2].exists())

    def test_concurrent_edit_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            f = self.fixture(Path(temp))
            with self.assertRaisesRegex(m.Blocked, "changed_during"):
                self.apply(f, prepare=lambda _: f[0].write_bytes(b"external-change"))
            self.assertEqual(f[0].read_bytes(), b"external-change")

    def test_rollback_and_repeat_restore_original(self):
        with tempfile.TemporaryDirectory() as temp:
            f = self.fixture(Path(temp))
            self.apply(f)
            self.assertEqual(m.rollback_reference(f[0], f[2])["state"], "rolled_back")
            self.assertEqual(f[0].read_bytes(), f[4])
            self.assertEqual(m.rollback_reference(f[0], f[2])["state"], "already_rolled_back")

    def test_rollback_does_not_overwrite_external_change(self):
        with tempfile.TemporaryDirectory() as temp:
            f = self.fixture(Path(temp))
            self.apply(f)
            f[0].write_bytes(b"external-change")
            with self.assertRaisesRegex(m.Blocked, "external_change"):
                m.rollback_reference(f[0], f[2])
            self.assertEqual(f[0].read_bytes(), b"external-change")

    def test_wrong_config_or_duplicate_command_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            f = self.fixture(Path(temp))
            for original, config in ((f[4], Path(temp) / "other.json"), (f[4] + f[4], f[3])):
                with self.assertRaises(m.Blocked):
                    m.replace_interpreter(original, f[1] / "python.exe", config)

    def test_archive_wrong_hash_and_path_fail_before_extraction(self):
        for filename in ("../outside", "folder/x", "C:payload"):
            data = io.BytesIO()
            with zipfile.ZipFile(data, "w") as archive:
                archive.writestr(filename, b"danger")
            raw = data.getvalue()
            with tempfile.TemporaryDirectory() as temp:
                destination = Path(temp)
                with self.assertRaisesRegex(m.Blocked, "digest_mismatch"):
                    m.extract_checked(raw, destination, "0" * 64)
                with self.assertRaisesRegex(m.Blocked, "path_invalid"):
                    m.extract_checked(raw, destination, m.digest(raw))
                self.assertEqual(list(destination.iterdir()), [])

    def test_valid_archive_extracts_only_expected_bytes(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr("python.exe", b"test-not-executable")
        raw = data.getvalue()
        with tempfile.TemporaryDirectory() as temp:
            m.extract_checked(raw, Path(temp), m.digest(raw))
            self.assertEqual((Path(temp) / "python.exe").read_bytes(), b"test-not-executable")

    def test_bundle_manifest_cannot_self_attest_changed_binary(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr("python.exe", b"original")
            archive.writestr("python312._pth", b".")
        raw = data.getvalue()
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(m, "ARCHIVE_SHA", m.digest(raw)):
            root = Path(temp)
            (root / "distribution.zip").write_bytes(raw)
            (root / "python.exe").write_bytes(b"changed")
            (root / "python312._pth").write_bytes(("python312.zip\n.\n" + str(m.ROOT) + "\n").encode())
            files = {p.name: m.digest(p.read_bytes()) for p in root.iterdir() if p.name != "distribution.zip"}
            (root / "integrity.json").write_text(json.dumps({"archive_sha256": m.ARCHIVE_SHA, "files": files}))
            with self.assertRaisesRegex(m.Blocked, "manifest_mismatch"):
                m.verify_bundle(root)

    def test_script_has_no_service_start_reboot_or_task_registration(self):
        source = Path(m.__file__).read_text(encoding="utf-8")
        self.assertNotIn("subprocess.Popen", source)
        self.assertNotIn("taskkill", source)
        self.assertNotIn("schtasks", source)
        self.assertNotIn("Restart-Computer", source)


if __name__ == "__main__":
    unittest.main()
