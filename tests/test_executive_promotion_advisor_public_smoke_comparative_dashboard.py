from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.inject_executive_promotion_advisor_public_smoke_comparative_card import (
    hydrate_runtime_index,
    patch_dashboard,
)
from scripts.validate_executive_promotion_advisor_public_smoke_comparative_card import validate


BASE_HTML = """<!doctype html>
<html><body><main></main><script>
function statusClass(value) { return value; }
async function renderRuntimeExecutiveIndex() {
  const payload = {};
  const fallback = {cards: {}};
  const cards = payload.cards || fallback.cards;
}
</script></body></html>
"""


class AdvisorPublicSmokeComparativeDashboardTests(unittest.TestCase):
    def test_injeta_estado_real_e_preserva_guardrails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dashboard = root / "index.html"
            runtime = root / "runtime-executive-index.json"
            state = root / "state.json"
            dashboard.write_text(BASE_HTML, encoding="utf-8")
            runtime.write_text(json.dumps({"production_ready": True, "cards": {}}), encoding="utf-8")
            state.write_text(json.dumps({
                "cards": {
                    "executive_promotion_advisor_public_smoke_comparative": {
                        "mode": "report-only",
                        "production_blocker": False,
                        "human_approval_required": True,
                        "environment_count": 3,
                        "required_environment_count": 3,
                        "complete_environment_coverage": True,
                        "weighted_pass_rate_percent": 99.0,
                        "minimum_pass_rate_percent": 98.0,
                        "minimum_stable_streak": 20,
                        "trend": "eligible-for-human-review",
                        "eligible_for_human_review": True,
                        "environments": {},
                    }
                }
            }), encoding="utf-8")

            hydrate_runtime_index(runtime, state)
            patch_dashboard(dashboard)
            evidence = validate(dashboard, runtime)
            payload = json.loads(runtime.read_text(encoding="utf-8"))

            self.assertTrue(payload["production_ready"])
            self.assertEqual(3, evidence["environment_count"])
            self.assertTrue(evidence["eligible_for_human_review"])
            self.assertFalse(evidence["production_blocker"])

    def test_fallback_e_idempotente(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dashboard = root / "index.html"
            runtime = root / "runtime-executive-index.json"
            state = root / "missing.json"
            dashboard.write_text(BASE_HTML, encoding="utf-8")
            runtime.write_text(json.dumps({"cards": {}}), encoding="utf-8")

            source = hydrate_runtime_index(runtime, state)
            patch_dashboard(dashboard)
            patch_dashboard(dashboard)
            evidence = validate(dashboard, runtime)
            html = dashboard.read_text(encoding="utf-8")

            self.assertEqual("safe-fallback", source)
            self.assertEqual(1, html.count('id="executive-promotion-advisor-public-smoke-comparative-card"'))
            self.assertEqual("insufficient-environment-coverage", evidence["trend"])
            self.assertFalse(evidence["eligible_for_human_review"])

    def test_normaliza_entrada_insegura(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime = root / "runtime.json"
            state = root / "state.json"
            runtime.write_text(json.dumps({"cards": {}}), encoding="utf-8")
            state.write_text(json.dumps({
                "cards": {
                    "executive_promotion_advisor_public_smoke_comparative": {
                        "mode": "blocking",
                        "production_blocker": True,
                        "human_approval_required": False,
                        "eligible_for_human_review": 1,
                        "complete_environment_coverage": 1,
                    }
                }
            }), encoding="utf-8")

            hydrate_runtime_index(runtime, state)
            card = json.loads(runtime.read_text(encoding="utf-8"))["cards"][
                "executive_promotion_advisor_public_smoke_comparative"
            ]
            self.assertEqual("report-only", card["mode"])
            self.assertFalse(card["production_blocker"])
            self.assertTrue(card["human_approval_required"])
            self.assertIsInstance(card["eligible_for_human_review"], bool)


if __name__ == "__main__":
    unittest.main()
