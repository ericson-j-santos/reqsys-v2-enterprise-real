import importlib.util
import json
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("ppc", ROOT / "scripts" / "personal_process_control.py")
ppc = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(ppc)


class PersonalProcessControlTests(unittest.TestCase):
    def setUp(self):
        base = ROOT / "governance" / "personal-process"
        self.demands = json.loads((base / "demandas.json").read_text(encoding="utf-8"))
        self.library = json.loads((base / "biblioteca.json").read_text(encoding="utf-8"))
        self.automations = json.loads((base / "automacoes.json").read_text(encoding="utf-8"))

    def test_seed_data_passes_governance(self):
        self.assertEqual([], ppc.validate_demands(self.demands))
        self.assertEqual([], ppc.validate_library(self.library))
        self.assertEqual([], ppc.validate_automations(self.automations))

    def test_open_item_requires_next_action(self):
        data = [dict(self.demands[0], proxima_acao="")]
        errors = ppc.validate_demands(data)
        self.assertTrue(any("sem proxima_acao" in error for error in errors))

    def test_completed_item_requires_evidence(self):
        data = [dict(self.demands[0], status="Concluido", evidencia="")]
        errors = ppc.validate_demands(data)
        self.assertTrue(any("concluido sem evidencia" in error for error in errors))

    def test_blocked_item_requires_blocker_type(self):
        data = [dict(self.demands[0], status="Bloqueado", tipo_bloqueio="Nenhum")]
        errors = ppc.validate_demands(data)
        self.assertTrue(any("bloqueado sem tipo_bloqueio" in error for error in errors))

    def test_pareto_is_deterministic(self):
        first = ppc.pareto(self.demands, ppc.demand_score)
        second = ppc.pareto(list(reversed(self.demands)), ppc.demand_score)
        self.assertEqual([x["id"] for x in first], [x["id"] for x in second])
        self.assertEqual("PROC-0001", first[0]["id"])
        self.assertEqual("P0 - Critica", ppc.priority(first[0]["indice"]))

    def test_monday_enables_deep_weekly_mode(self):
        snapshot, _ = ppc.build_snapshot(self.demands, self.library, self.automations, date(2026, 9, 7))
        self.assertEqual("semanal_aprofundado", snapshot["mode"])

    def test_non_monday_uses_daily_mode(self):
        snapshot, _ = ppc.build_snapshot(self.demands, self.library, self.automations, date(2026, 9, 3))
        self.assertEqual("diario", snapshot["mode"])

    def test_input_hash_is_order_independent_for_object_keys(self):
        self.assertEqual(ppc.canonical_sha256({"b": 2, "a": 1}), ppc.canonical_sha256({"a": 1, "b": 2}))

    def test_xlsx_is_valid_zip_with_expected_sheets(self):
        snapshot, _ = ppc.build_snapshot(self.demands, self.library, self.automations, date(2026, 9, 3))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.xlsx"
            ppc.write_xlsx(path, snapshot, self.demands, self.library, self.automations)
            with zipfile.ZipFile(path) as zf:
                self.assertIsNone(zf.testzip())
                names = set(zf.namelist())
                self.assertIn("xl/workbook.xml", names)
                self.assertIn("xl/worksheets/sheet4.xml", names)

    def test_same_inputs_and_date_produce_same_xlsx(self):
        snapshot, _ = ppc.build_snapshot(self.demands, self.library, self.automations, date(2026, 9, 3))
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "a.xlsx"
            second = Path(tmp) / "b.xlsx"
            ppc.write_xlsx(first, snapshot, self.demands, self.library, self.automations)
            ppc.write_xlsx(second, snapshot, self.demands, self.library, self.automations)
            self.assertEqual(first.read_bytes(), second.read_bytes())


if __name__ == "__main__":
    unittest.main()
