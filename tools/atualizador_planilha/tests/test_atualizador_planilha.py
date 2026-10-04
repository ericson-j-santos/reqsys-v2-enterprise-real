import csv
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from atualizador_planilha import SpreadsheetError, TransformRule, generate_portable_package, read_records, transform_file


class AtualizadorPlanilhaTests(unittest.TestCase):
    def test_csv_to_json_with_multiple_rules(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "entrada.csv"
            destination = Path(temp) / "saida.json"
            source.write_text("nome,cidade\n  ana  ,sao paulo\n", encoding="utf-8")
            count = transform_file(source, destination, [TransformRule("nome", "trim"), TransformRule("cidade", "upper")])
            self.assertEqual(1, count)
            self.assertEqual([{"nome": "ana", "cidade": "SAO PAULO"}], json.loads(destination.read_text(encoding="utf-8")))

    def test_json_to_csv_preserves_union_of_columns(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "entrada.json"
            destination = Path(temp) / "saida.csv"
            source.write_text('[{"a": 1}, {"a": 2, "b": 3}]', encoding="utf-8")
            transform_file(source, destination, [TransformRule("status", "set", "ok")])
            with destination.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(["a", "status", "b"], list(rows[0].keys()))
            self.assertEqual("ok", rows[1]["status"])

    def test_replace_requires_separator(self):
        with self.assertRaises(SpreadsheetError):
            TransformRule("nome", "replace", "invalido").apply({"nome": "abc"})

    def test_rejects_unsupported_extension(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "entrada.txt"
            path.write_text("x", encoding="utf-8")
            with self.assertRaises(SpreadsheetError):
                read_records(path)

    def test_generates_portable_zip(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = generate_portable_package(Path(temp) / "pacote.zip")
            self.assertTrue(archive.is_file())
            with zipfile.ZipFile(archive) as bundle:
                names = set(bundle.namelist())
            self.assertIn("atualizador_planilha_portatil/atualizador_planilha.py", names)
            self.assertIn("atualizador_planilha_portatil/executar.bat", names)
            self.assertIn("atualizador_planilha_portatil/README.txt", names)


if __name__ == "__main__":
    unittest.main()
