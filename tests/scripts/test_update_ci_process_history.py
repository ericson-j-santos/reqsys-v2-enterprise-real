import tempfile
import unittest
from pathlib import Path

from scripts.update_ci_process_history import history_record, load_history, merge_history, write_history


class ProcessHistoryTests(unittest.TestCase):
    def test_record_preserves_report_only_governance(self):
        record = history_record({"generated_at":"2026-09-03T00:00:00Z","run_id":"1","baseline_comparison":{"available":True,"overall_signal":"improved","delta":{"p95_seconds":-5},"mode":"report-only","creates_gate":False}})
        self.assertEqual(record["baseline_comparison"]["mode"], "report-only")
        self.assertFalse(record["baseline_comparison"]["creates_gate"])

    def test_merge_is_idempotent_by_run_id(self):
        first = {"generated_at":"2026-09-03T00:00:00Z","run_id":"1"}
        second = {"generated_at":"2026-09-03T01:00:00Z","run_id":"1"}
        merged = merge_history([first], second)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["generated_at"], second["generated_at"])

    def test_merge_trims_old_records(self):
        records = [{"generated_at":f"2026-09-03T{i:02d}:00:00Z","run_id":str(i)} for i in range(4)]
        merged = merge_history(records, {"generated_at":"2026-09-03T05:00:00Z","run_id":"5"}, max_records=3)
        self.assertEqual(len(merged), 3)
        self.assertEqual(merged[-1]["run_id"], "5")

    def test_roundtrip_jsonl(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "history.jsonl"
            records = [{"generated_at":"2026-09-03T00:00:00Z","run_id":"1"}]
            write_history(path, records)
            self.assertEqual(load_history(path), records)


if __name__ == "__main__":
    unittest.main()
