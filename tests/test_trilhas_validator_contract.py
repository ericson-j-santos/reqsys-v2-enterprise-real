"""Consolidação nunca converte validador aposentado ou inválido em verde."""
from __future__ import annotations
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import trilhas_padrao_ouro as module


class TestConsolidatedValidatorContract(unittest.TestCase):
    def test_status_unknown_blocks(self):
        for status in ("retired", "skipped", "unknown", "config_only", "failed"):
            self.assertEqual(module.trail_status({"adr": True}, [], status), "failed")
        self.assertEqual(module.trail_status({"adr": True}, [], "passed_with_warnings"), "passed_with_warnings")

    def test_subprocess_invalid_outputs_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "mock.py").write_text("# fixture", encoding="utf-8")
            trail = {"id": "trilha-a", "validator": "mock.py"}
            for body, code in [("",0),("{",0),('{"status":"retired"}',0),('{"status":"passed"}',1),("null",0)]:
                with patch.object(module, "ROOT", root), patch.object(module.subprocess, "run", return_value=subprocess.CompletedProcess([], code, stdout=body, stderr="failure")):
                    status,_ = module.run_validator(trail)
                    self.assertEqual(status, "failed", repr(body))

    def test_warning_is_not_healthy(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root / "mock.py").write_text("# fixture", encoding="utf-8")
            with patch.object(module, "ROOT", root), patch.object(module.subprocess, "run", return_value=subprocess.CompletedProcess([],0,stdout='{"status":"passed_with_warnings","summary":{"physical_e2e_verified":false}}',stderr="")):
                status, evidence=module.run_validator({"id":"trilha-a","validator":"mock.py"})
                self.assertEqual(status, "passed_with_warnings")
                self.assertFalse(evidence["summary"]["physical_e2e_verified"])


if __name__ == "__main__":
    unittest.main()
