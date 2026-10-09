"""Validacao de identidade e precondicoes do teste controlado do worker."""
import copy
import unittest
from scripts import noteri_worker_recovery_test as m


class RecoveryTests(unittest.TestCase):
    def snapshot(self):
        return {"unreadable_python_processes": 0, "processes": [
            {"role": "supervisor", "pid": 10, "ppid": 1, "created_at": 100},
            {"role": "worker", "pid": 11, "ppid": 10, "created_at": 101}]}

    def test_replacement_preserves_supervisor(self):
        before = self.snapshot()
        after = copy.deepcopy(before)
        after["processes"][1].update(pid=12, created_at=102)
        self.assertTrue(m.replaced(before, after))

    def test_unchanged_worker_is_not_recovery(self):
        before = self.snapshot()
        self.assertFalse(m.replaced(before, copy.deepcopy(before)))

    def test_temporary_absence_is_not_success(self):
        before = self.snapshot()
        after = copy.deepcopy(before)
        after["processes"].pop()
        self.assertFalse(m.replaced(before, after))

    def test_supervisor_replacement_is_blocked(self):
        before = self.snapshot()
        after = copy.deepcopy(before)
        after["processes"][0]["created_at"] = 103
        with self.assertRaisesRegex(m.Blocked, "supervisor_changed"):
            m.replaced(before, after)

    def test_wrong_worker_parent_is_blocked(self):
        snapshot = self.snapshot()
        snapshot["processes"][1]["ppid"] = 99
        with self.assertRaisesRegex(m.Blocked, "worker_parent_mismatch"):
            m.pair(snapshot)

    def test_duplicate_worker_is_blocked(self):
        snapshot = self.snapshot()
        snapshot["processes"].append(copy.deepcopy(snapshot["processes"][1]))
        with self.assertRaisesRegex(m.Blocked, "not_unique"):
            m.pair(snapshot)

    def test_unreadable_identity_is_blocked(self):
        snapshot = self.snapshot()
        snapshot["unreadable_python_processes"] = 1
        with self.assertRaisesRegex(m.Blocked, "unreadable"):
            m.pair(snapshot)

    def test_only_study_and_operational_worker(self):
        good = {"profile": "ESTUDO", "fresh": True, "auth_valid": True,
                "controller_online": True, "profile_capable": True}
        m.require_study(good, "ESTUDO")
        for key in ("fresh", "auth_valid", "controller_online", "profile_capable"):
            with self.assertRaises(m.Blocked):
                m.require_study({**good, key: False}, "ESTUDO")
        with self.assertRaises(m.Blocked):
            m.require_study(good, "NORMAL")

    def test_host_and_confirmation_negative_controls(self):
        args = ("a"*40, "recovery-proof", m.CONFIRM)
        m.validate_identity(*args, host="Noteri", platform="nt")
        with self.assertRaises(m.Blocked):
            m.validate_identity(*args, host="Desktop", platform="nt")
        with self.assertRaises(m.Blocked):
            m.validate_identity("a"*40, "recovery-proof", "INVALID", host="Noteri", platform="nt")

    def test_identity_helpers_are_idempotent(self):
        snapshot = self.snapshot()
        original = copy.deepcopy(snapshot)
        self.assertEqual(m.pair(snapshot), m.pair(snapshot))
        self.assertEqual(snapshot, original)


if __name__ == "__main__":
    unittest.main()
