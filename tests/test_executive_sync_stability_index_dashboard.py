from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "inject_executive_sync_stability_index_card.py"
spec = importlib.util.spec_from_file_location("inject_sync_index", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


class ExecutiveSyncStabilityIndexDashboardTest(unittest.TestCase):
    def test_normalizes_guardrails_and_preserves_metrics(self) -> None:
        card = module.normalize({"cards": {"executive_sync_stability_index": {
            "status": "stable",
            "score": 98.5,
            "environment_coverage": 100,
            "total_samples": 90,
            "weighted_pass_rate": 99.1,
            "weighted_sync_rate": 98.9,
            "minimum_stable_sequence": 30,
            "mode": "blocking",
            "production_blocker": True,
            "human_approval_required": False,
        }}})
        self.assertEqual(card["status"], "stable")
        self.assertEqual(card["score"], 98.5)
        self.assertEqual(card["mode"], "report-only")
        self.assertFalse(card["production_blocker"])
        self.assertTrue(card["human_approval_required"])

    def test_safe_fallback(self) -> None:
        card = module.normalize({})
        self.assertEqual(card["status"], "insufficient-environment-coverage")
        self.assertEqual(card["score"], 0.0)
        self.assertFalse(card["production_blocker"])

    def test_injection_is_idempotent(self) -> None:
        html = f"<html><main>{module.HOOK}</main></html>"
        card_html = module.render_card(module.normalize({}))
        once = module.inject(html, card_html)
        twice = module.inject(once, card_html)
        self.assertEqual(once, twice)
        self.assertEqual(twice.count(f'id="{module.CARD_ID}"'), 1)

    def test_runtime_state_outside_card_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runtime.json"
            payload = {"production_ready": True, "decision": "REVIEW", "cards": {}}
            path.write_text(json.dumps(payload), encoding="utf-8")
            data = json.loads(path.read_text(encoding="utf-8"))
            data.setdefault("cards", {})["executive_sync_stability_index"] = module.normalize(data)
            self.assertTrue(data["production_ready"])
            self.assertEqual(data["decision"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
