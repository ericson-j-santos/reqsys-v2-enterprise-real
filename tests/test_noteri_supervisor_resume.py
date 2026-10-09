"""Controles negativos e idempotência da retomada do supervisor."""
import copy
import unittest
from pathlib import Path
from scripts import noteri_supervisor_resume as m


def proc(role="supervisor", pid=20, ppid=1):
    return {"role": role, "pid": pid, "ppid": ppid, "created_at": 123.0}


class ResumeTests(unittest.TestCase):
    def test_absent_allows_one_start(self):
        self.assertEqual(m.decision({"processes": [], "unreadable_python_processes": 0}), "absent")

    def test_existing_supervisor_suppresses_duplicate(self):
        self.assertEqual(m.decision({"processes": [proc()], "unreadable_python_processes": 0}), "existing")

    def test_exact_child_is_accepted(self):
        x = {"processes": [proc(), proc("worker", 21, 20)], "unreadable_python_processes": 0}
        self.assertEqual(m.decision(x), "existing")

    def test_duplicate_supervisor_is_rejected(self):
        with self.assertRaisesRegex(m.Blocked, "multiple_runtime_processes"):
            m.decision({"processes": [proc(), proc(pid=22)], "unreadable_python_processes": 0})

    def test_orphan_worker_is_rejected(self):
        with self.assertRaisesRegex(m.Blocked, "worker_parent"):
            m.decision({"processes": [proc("worker")], "unreadable_python_processes": 0})

    def test_unknown_identity_blocks_start(self):
        with self.assertRaisesRegex(m.Blocked, "identity_unreadable"):
            m.decision({"processes": [], "unreadable_python_processes": 1})

    def test_replay_is_read_only(self):
        value = {"processes": [proc()], "unreadable_python_processes": 0}
        original = copy.deepcopy(value)
        self.assertEqual(m.decision(value), m.decision(value))
        self.assertEqual(value, original)

    def valid_row(self):
        return {"exe": str(m.PYTHON), "cwd": str(m.ROOT),
                "cmdline": [str(m.PYTHON), "-B", "-m", "scripts.service_supervisor",
                            "--config", str(m.ROOT / "service-config.json")]}

    def test_process_path_args_and_cwd_are_checked(self):
        self.assertEqual(m.role(self.valid_row()), "supervisor")

    def test_wrong_python_cannot_be_adopted(self):
        row = self.valid_row()
        row["exe"] = "C:/other/python.exe"
        with self.assertRaisesRegex(m.Blocked, "identity_mismatch"):
            m.role(row)

    def test_wrong_cwd_cannot_be_adopted(self):
        row = self.valid_row()
        row["cwd"] = "C:/other"
        with self.assertRaisesRegex(m.Blocked, "identity_mismatch"):
            m.role(row)

    def test_extra_arguments_cannot_be_adopted(self):
        row = self.valid_row()
        row["cmdline"].append("--other")
        with self.assertRaisesRegex(m.Blocked, "identity_mismatch"):
            m.role(row)

    def test_different_runtime_is_untouched(self):
        row = self.valid_row()
        row["cmdline"][-1] = "C:/other/service-config.json"
        row["cwd"] = "C:/other"
        self.assertIsNone(m.role(row))

    def test_unverified_library_is_rejected(self):
        with self.assertRaisesRegex(m.Blocked, "digest_mismatch"):
            m.wheel_entries(b"not a verified wheel")

    def test_no_legacy_forced_termination_or_profile_change(self):
        source = (Path(__file__).parents[1] / "scripts/noteri_supervisor_resume.py").read_text()
        for forbidden in ("taskkill", "os.kill(", "shell=True", "reboot_once(", "set_host_profile("):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
