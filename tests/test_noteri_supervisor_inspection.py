"""Regression controls for the read-only supervisor inspection."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import noteri_supervisor_inspection as m


class InspectionTests(unittest.TestCase):
    def fixture(self, base: Path):
        runtime, appdata, local = base / "runtime", base / "appdata", base / "local"
        runtime.mkdir()
        (runtime / "worker-config.json").write_text(json.dumps({
            "worker_id": "noteri", "endpoint": "http://DESKTOP-PDQK954:8787",
            "heartbeat_interval_seconds": 20, "secret": "do-not-publish"}))
        (runtime / "service-config.json").write_text(json.dumps({
            "mode": "worker", "install_root": str(runtime),
            "worker_config": str(runtime / "worker-config.json")}))
        (runtime / "runtime-status.json").write_text(json.dumps({
            "updated_at_epoch": 100, "supervisor_pid": 123, "worker_pid": None}))
        startup = appdata / "Microsoft/Windows/Start Menu/Programs/Startup"
        startup.mkdir(parents=True)
        return runtime, appdata, local, startup

    def test_valid_configuration_is_sanitized(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, appdata, local, _ = self.fixture(Path(tmp))
            report = m.inspect_layout(runtime, appdata, local, 150)
            self.assertTrue(report["worker_config"]["endpoint_expected"])
            self.assertTrue(report["supervisor_config"]["install_root_expected"])
            self.assertNotIn("do-not-publish", json.dumps(report))
            self.assertNotIn('"secret"', json.dumps(report))
            self.assertEqual(report["runtime_status"]["age_seconds"], 50)
            self.assertFalse(report["runtime_status"]["pid_liveness_verified"])

    def test_missing_runtime_does_not_invent_installation(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            report = m.inspect_layout(base / "absent", base / "a", base / "b", 100)
            self.assertFalse(report["runtime_exists"])
            self.assertEqual(report["worker_config"]["state"], "missing")

    def test_missing_startup_python_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, appdata, local, startup = self.fixture(Path(tmp))
            missing = Path(tmp) / "python.exe"
            (startup / "ReqSys-Orchestrator-noteri.cmd").write_text(
                f'"{missing}" -m scripts.service_supervisor --config "opaque"\n')
            report = m.inspect_layout(runtime, appdata, local, 150)
            self.assertEqual(report["startup"]["interpreter_file_state"], "missing")

    def test_present_python_is_not_executed_or_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, appdata, local, startup = self.fixture(Path(tmp))
            binary = Path(tmp) / "python.exe"
            binary.write_bytes(b"x" * (m.LIMIT + 1))
            (startup / "ReqSys-Orchestrator-noteri.cmd").write_text(
                f'"{binary}" -m scripts.service_supervisor --config "opaque"\n')
            report = m.inspect_layout(runtime, appdata, local, 150)
            self.assertEqual(report["startup"]["interpreter_file_state"], "present")

    def test_malformed_json_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text("not json")
            metadata, payload = m.read_object(path)
            self.assertFalse(metadata["json_valid"])
            self.assertEqual(payload, {})

    def test_oversized_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data"
            path.write_bytes(b"x" * (m.LIMIT + 1))
            self.assertEqual(m.read_fixed(path)[0]["state"], "type_or_size_rejected")

    def test_link_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            target, link = Path(tmp) / "target", Path(tmp) / "link"
            target.write_text("private")
            try:
                link.symlink_to(target)
            except OSError:
                self.skipTest("symlink creation unavailable")
            self.assertEqual(m.read_fixed(link)[0]["state"], "link_rejected")

    def test_repeated_read_does_not_modify_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            runtime, appdata, local, _ = self.fixture(base)
            before = {str(p): p.read_bytes() for p in base.rglob("*") if p.is_file()}
            first = m.inspect_layout(runtime, appdata, local, 150)
            self.assertEqual(first, m.inspect_layout(runtime, appdata, local, 150))
            self.assertEqual(before, {str(p): p.read_bytes() for p in base.rglob("*") if p.is_file()})


if __name__ == "__main__":
    unittest.main()
