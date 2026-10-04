import copy
import importlib.util
import json
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "ppc",
    ROOT / "scripts/personal_process_control.py",
)
ppc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ppc)


class Tests(unittest.TestCase):
    def setUp(self):
        base = ROOT / "governance/personal-process"
        self.d = json.loads((base / "demandas.json").read_text(encoding="utf-8"))
        self.l = json.loads((base / "biblioteca.json").read_text(encoding="utf-8"))
        self.a = json.loads((base / "automacoes.json").read_text(encoding="utf-8"))

    def test_seed(self):
        self.assertEqual([], ppc.validate_demands(self.d))
        self.assertEqual([], ppc.validate_library(self.l))
        self.assertEqual([], ppc.validate_automations(self.a))
        self.assertTrue(all(x["id"].startswith("EXT-") for x in self.d))

    def test_status_model_and_blocker(self):
        item = next(x for x in self.d if x["id"] == "EXT-001")
        self.assertEqual("Bloqueada externamente", item["status"])
        self.assertEqual("Humano", item["tipo_bloqueio"])
        self.assertTrue(item["responsavel_bloqueio"])
        self.assertEqual(
            "https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/1420",
            item["evidencia"],
        )

    def test_open_item_requires_next_action(self):
        item = dict(self.d[1], proxima_acao="")
        errors = ppc.validate_demands([item] + self.d[2:])
        self.assertTrue(any("sem proxima_acao" in error for error in errors))

    def test_concluded_requires_evidence(self):
        item = dict(self.d[1], status="Concluido", evidencia="")
        errors = ppc.validate_demands([self.d[0], item] + self.d[2:])
        self.assertTrue(any("concluido sem evidencia" in error for error in errors))

    def test_external_block_requires_owner(self):
        item = dict(self.d[0], responsavel_bloqueio="")
        errors = ppc.validate_demands([item] + self.d[1:])
        self.assertTrue(
            any("sem responsavel_bloqueio" in error for error in errors)
        )

    def test_wip_limit_blocks_four_active_items(self):
        data = copy.deepcopy(self.d)
        for index in (1, 2):
            data[index]["status"] = "Em execucao"
        errors = ppc.validate_demands(data)
        self.assertTrue(any("WIP excedido" in error for error in errors))

    def test_dependency_must_exist(self):
        data = copy.deepcopy(self.d)
        data[1]["dependencias"] = ["EXT-999"]
        errors = ppc.validate_demands(data)
        self.assertTrue(any("dependencia inexistente" in error for error in errors))

    def test_duplicate_requires_valid_target(self):
        data = copy.deepcopy(self.d)
        data[5]["status"] = "Duplicada"
        data[5]["duplicado_de"] = "EXT-999"
        errors = ppc.validate_demands(data)
        self.assertTrue(any("duplicado_de inexistente" in error for error in errors))

    def test_aging_escalates(self):
        item = copy.deepcopy(self.d[5])
        item["ultima_movimentacao_em"] = "2026-08-01"
        self.assertEqual(44, ppc.aging_days(item, date(2026, 9, 14)))
        self.assertEqual("critico", ppc.aging_level(44))
        self.assertEqual(5, ppc.aging_urgency(44))

    def test_dependency_increases_unlock_factor(self):
        data = copy.deepcopy(self.d)
        data[2]["dependencias"] = ["EXT-002"]
        data[5]["dependencias"] = ["EXT-002"]
        self.assertEqual(3, ppc.dependency_unlock_factor("EXT-002", data))

    def test_priority_formula_is_deterministic(self):
        first = ppc.demand_score(self.d[1], self.d, date(2026, 9, 14))
        second = ppc.demand_score(self.d[1], list(reversed(self.d)), date(2026, 9, 14))
        self.assertEqual(first, second)
        self.assertEqual(12.5, first)

    def test_next_increment_uses_available_wip_for_highest_score(self):
        snapshot, _ = ppc.build_snapshot(
            self.d,
            self.l,
            self.a,
            date(2026, 9, 14),
        )
        self.assertEqual(2, snapshot["governance"]["wip_current"])
        self.assertEqual("EXT-002", snapshot["next_increment"]["id"])

    def test_when_wip_is_full_only_active_items_are_selected(self):
        data = copy.deepcopy(self.d)
        data[2]["status"] = "Em execucao"
        snapshot, _ = ppc.build_snapshot(
            data,
            self.l,
            self.a,
            date(2026, 9, 14),
        )
        self.assertEqual(3, snapshot["governance"]["wip_current"])
        self.assertIn(
            snapshot["next_increment"]["id"],
            {"EXT-003", "EXT-004", "EXT-005"},
        )

    def test_modes(self):
        self.assertEqual(
            "semanal_aprofundado",
            ppc.build_snapshot(
                self.d, self.l, self.a, date(2026, 9, 14)
            )[0]["mode"],
        )
        self.assertEqual(
            "diario",
            ppc.build_snapshot(
                self.d, self.l, self.a, date(2026, 9, 15)
            )[0]["mode"],
        )

    def test_hash_is_canonical(self):
        self.assertEqual(
            ppc.canonical_sha256({"b": 2, "a": 1}),
            ppc.canonical_sha256({"a": 1, "b": 2}),
        )

    def test_history_is_idempotent_and_ordered(self):
        s1, p1 = ppc.build_snapshot(
            self.d, self.l, self.a, date(2026, 9, 14)
        )
        s2, p2 = ppc.build_snapshot(
            self.d, self.l, self.a, date(2026, 9, 15)
        )
        h = ppc.merge_history([], ppc.history_record(s2, p2))
        h = ppc.merge_history(h, ppc.history_record(s1, p1))
        h = ppc.merge_history(h, ppc.history_record(s1, p1))
        self.assertEqual(
            ["2026-09-14", "2026-09-15"],
            [x["as_of"] for x in h],
        )

    def test_recurrence_becomes_automation_candidate(self):
        snapshot, report = ppc.build_snapshot(
            self.d,
            self.l,
            self.a,
            date(2026, 9, 14),
        )
        history = []
        for day in ("2026-09-12", "2026-09-13", "2026-09-14"):
            record = ppc.history_record(snapshot, report)
            record["as_of"] = day
            history = ppc.merge_history(history, record)
        recurrence = ppc.recurrence_summary(history, report)
        ids = {item["id"] for item in recurrence["candidatos_automacao"]}
        self.assertIn("EXT-002", ids)
        self.assertNotIn("EXT-001", ids)

    def test_xlsx_is_deterministic(self):
        snapshot, report = ppc.build_snapshot(
            self.d,
            self.l,
            self.a,
            date(2026, 9, 14),
        )
        history = ppc.merge_history(
            [],
            ppc.history_record(snapshot, report),
        )
        ppc.apply_recurrence(snapshot, report, history)
        with tempfile.TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "a.xlsx"
            second = Path(temp_dir) / "b.xlsx"
            ppc.write_xlsx(
                first,
                snapshot,
                self.d,
                self.l,
                self.a,
                history,
            )
            ppc.write_xlsx(
                second,
                snapshot,
                self.d,
                self.l,
                self.a,
                history,
            )
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                self.assertIsNone(archive.testzip())
                self.assertIn("xl/worksheets/sheet5.xml", archive.namelist())


if __name__ == "__main__":
    unittest.main()
