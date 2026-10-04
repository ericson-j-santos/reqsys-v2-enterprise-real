import importlib.util
import sys
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "js_performance_gate.py"
SPEC = importlib.util.spec_from_file_location("js_performance_gate", MODULE_PATH)
gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gate
assert SPEC.loader is not None
SPEC.loader.exec_module(gate)

SYNC_READ = "readFile" + "Sync"


class JsPerformanceGateTests(unittest.TestCase):
    def test_sync_fs_blocks_runtime_code(self):
        findings = gate.analyze_text(
            Path("frontend/src/service.js"),
            f"const value = {SYNC_READ}('data.json', 'utf8');",
        )
        active = [item for item in findings if not item.suppressed]
        self.assertTrue(any(item.rule_id == "PERF001" and item.severity == "error" for item in active))

    def test_sync_fs_outside_runtime_is_advisory(self):
        findings = gate.analyze_text(
            Path("scripts/build-index.mjs"),
            f"const value = {SYNC_READ}('data.json', 'utf8');",
        )
        self.assertTrue(any(item.rule_id == "PERF001" and item.severity == "warning" for item in findings))
        self.assertFalse(any(item.severity == "error" for item in findings))

    def test_http_handler_sync_operation_is_explicit_blocker(self):
        findings = gate.analyze_text(
            Path("server/routes/users.ts"),
            f"router.get('/users', (req, res) => {{ const x = {SYNC_READ}('users.json'); res.send(x); }});",
        )
        self.assertTrue(any(item.rule_id == "PERF006" and item.severity == "error" for item in findings))

    def test_chained_array_transforms_are_warning(self):
        findings = gate.analyze_text(
            Path("frontend/src/list.js"),
            "const result = rows.map(x => x.value).filter(Boolean).reduce((a, b) => a + b, 0);",
        )
        self.assertTrue(any(item.rule_id == "PERF004" and item.severity == "warning" for item in findings))

    def test_excessive_console_is_warning(self):
        text = "\n".join("console.log(item);" for _ in range(9))
        findings = gate.analyze_text(Path("frontend/src/debug.js"), text, console_threshold=8)
        self.assertTrue(any(item.rule_id == "PERF005" for item in findings))

    def test_valid_suppression_requires_reason(self):
        text = (
            "// performance-gate: allow PERF001 reason=bootstrap executa antes de aceitar trafego\n"
            f"const value = {SYNC_READ}('config.json', 'utf8');"
        )
        findings = gate.analyze_text(Path("server/bootstrap.js"), text)
        perf001 = next(item for item in findings if item.rule_id == "PERF001")
        self.assertTrue(perf001.suppressed)

    def test_short_suppression_reason_is_rejected(self):
        text = (
            "// performance-gate: allow PERF001 reason=legacy\n"
            f"const value = {SYNC_READ}('config.json', 'utf8');"
        )
        findings = gate.analyze_text(Path("server/bootstrap.js"), text)
        perf001 = next(item for item in findings if item.rule_id == "PERF001")
        self.assertFalse(perf001.suppressed)

    def test_test_and_config_files_are_excluded(self):
        self.assertTrue(gate._is_excluded(Path("frontend/src/a.test.js")))
        self.assertTrue(gate._is_excluded(Path("frontend/vite.config.js")))
        self.assertTrue(gate._is_excluded(Path("server/tests/a.js")))


if __name__ == "__main__":
    unittest.main()
