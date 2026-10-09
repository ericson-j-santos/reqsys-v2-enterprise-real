"""Contratos de resposta do E2E; nao simulam homologacao fisica."""
import unittest
from scripts import noteri_profile_control_e2e as m


class ProfileControlTests(unittest.TestCase):
    def test_normal(self):
        m.validate_data({"host": "Noteri", "profile": "NORMAL", "accepts_new_development": True}, "NORMAL")

    def test_estudo(self):
        m.validate_data({"host": "Noteri", "profile": "ESTUDO", "accepts_new_development": False}, "ESTUDO")

    def test_other_host(self):
        with self.assertRaises(m.proc.Blocked):
            m.validate_data({"host": "OTHER", "profile": "NORMAL", "accepts_new_development": True}, "NORMAL")

    def test_wrong_profile(self):
        with self.assertRaises(m.proc.Blocked):
            m.validate_data({"host": "Noteri", "profile": "ESTUDO", "accepts_new_development": False}, "NORMAL")

    def test_wrong_admission(self):
        with self.assertRaises(m.proc.Blocked):
            m.validate_data({"host": "Noteri", "profile": "NORMAL", "accepts_new_development": False}, "NORMAL")


if __name__ == "__main__":
    unittest.main()
