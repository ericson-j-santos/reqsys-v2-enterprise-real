from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.inject_executive_promotion_advisor_homologation_trend_card import (
    hydrate_contract,
    patch_dashboard,
)
from scripts.validate_executive_promotion_advisor_homologation_trend_card import validate


BASE_HTML = '''<html><body><main>
<section class="card"><h2>Base</h2></section>
</main>
<script>
function addLink() {}
async function renderRuntimeExecutiveIndex() {
  const payload = {};
  const fallback = {cards: {}};
  const cards = payload.cards || fallback.cards;
  return cards;
}
</script></body></html>
'''


class AdvisorTrendDashboardTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.dashboard = root / "index.html"
        self.runtime = root / "runtime-executive-index.json"
        self.state = root / "state-runtime-executive-index.json"
        self.dashboard.write_text(BASE_HTML, encoding="utf-8")
        self.runtime.write_text(json.dumps({
            "production_ready": True,
            "cards": {},
            "links": {},
            "guardrails": [],
        }), encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_hydrates_real_trend_and_preserves_production_state(self) -> None:
        self.state.write_text(json.dumps({
            "cards": {
                "executive_promotion_advisor_homologation_trend": {
                    "mode": "report-only",
                    "production_blocker": False,
                    "human_approval_required": True,
                    "sample_count": 30,
                    "full_homologation_rate_percent": 100.0,
                    "stable_streak": 30,
                    "latest_decision": "HOMOLOGATED",
                    "eligible_for_gate_review": True,
                    "trend": "eligible-for-human-review",
                    "source": "history.json",
                }
            }
        }), encoding="utf-8")

        source = hydrate_contract(self.runtime, self.state)
        patch_dashboard(self.dashboard)
        evidence = validate(self.dashboard, self.runtime)
        runtime = json.loads(self.runtime.read_text(encoding="utf-8"))

        self.assertEqual(source, str(self.state))
        self.assertTrue(runtime["production_ready"])
        self.assertTrue(evidence["eligible_for_gate_review"])
        self.assertFalse(evidence["production_blocker"])
        self.assertTrue(evidence["human_approval_required"])

    def test_fallback_is_non_blocking_and_not_eligible(self) -> None:
        hydrate_contract(self.runtime, None)
        patch_dashboard(self.dashboard)
        evidence = validate(self.dashboard, self.runtime)
        self.assertEqual(evidence["trend"], "insufficient-data")
        self.assertFalse(evidence["eligible_for_gate_review"])
        self.assertFalse(evidence["production_blocker"])

    def test_patch_is_idempotent(self) -> None:
        hydrate_contract(self.runtime, None)
        patch_dashboard(self.dashboard)
        first = self.dashboard.read_text(encoding="utf-8")
        patch_dashboard(self.dashboard)
        second = self.dashboard.read_text(encoding="utf-8")
        self.assertEqual(first, second)
        self.assertEqual(first.count('id="executive-promotion-advisor-homologation-trend-card"'), 1)

    def test_normalizes_unsafe_source_guardrails(self) -> None:
        self.state.write_text(json.dumps({
            "cards": {
                "executive_promotion_advisor_homologation_trend": {
                    "mode": "blocking",
                    "production_blocker": True,
                    "human_approval_required": False,
                    "eligible_for_gate_review": True,
                }
            }
        }), encoding="utf-8")
        hydrate_contract(self.runtime, self.state)
        card = json.loads(self.runtime.read_text(encoding="utf-8"))["cards"][
            "executive_promotion_advisor_homologation_trend"
        ]
        self.assertEqual(card["mode"], "report-only")
        self.assertFalse(card["production_blocker"])
        self.assertTrue(card["human_approval_required"])


if __name__ == "__main__":
    unittest.main()
