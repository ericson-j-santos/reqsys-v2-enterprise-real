import json
import tempfile
import unittest
from pathlib import Path

from scripts.inject_executive_promotion_advisor_card import patch_dashboard
from scripts.validate_executive_promotion_advisor_card import validate

BASE_HTML = '''<!doctype html><html><body><main></main><script>
function statusClass(value) { return value || 'unknown'; }
async function renderRuntimeExecutiveIndex() {
  const payload = {cards: {}};
  const fallback = {cards: {}};
  const cards = payload.cards || fallback.cards;
  return cards;
}
</script></body></html>'''


class ExecutivePromotionAdvisorCardTests(unittest.TestCase):
    def test_injects_card_idempotently(self):
        with tempfile.TemporaryDirectory() as directory:
            dashboard = Path(directory) / "index.html"
            dashboard.write_text(BASE_HTML, encoding="utf-8")
            patch_dashboard(dashboard)
            first = dashboard.read_text(encoding="utf-8")
            patch_dashboard(dashboard)
            second = dashboard.read_text(encoding="utf-8")
            self.assertEqual(first, second)
            self.assertEqual(second.count('id="executive-promotion-advisor-card"'), 1)

    def test_validates_packaged_contract_and_guardrails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dashboard = root / "index.html"
            runtime = root / "runtime-executive-index.json"
            dashboard.write_text(BASE_HTML, encoding="utf-8")
            patch_dashboard(dashboard)
            runtime.write_text(json.dumps({"cards": {"executive_promotion_advisor": {
                "decision": "REVIEW",
                "status": "yellow",
                "confidence_percent": 70,
                "mode": "report-only",
                "production_blocker": False,
                "human_approval_required": True,
                "risk_domains": ["runtime"],
            }}}), encoding="utf-8")
            result = validate(dashboard, runtime)
            self.assertEqual(result["status"], "passed")
            self.assertTrue(result["contract_validated"])

    def test_rejects_automatic_production_blocking(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dashboard = root / "index.html"
            runtime = root / "runtime-executive-index.json"
            dashboard.write_text(BASE_HTML, encoding="utf-8")
            patch_dashboard(dashboard)
            runtime.write_text(json.dumps({"cards": {"executive_promotion_advisor": {
                "mode": "report-only",
                "production_blocker": True,
                "human_approval_required": True,
            }}}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "não pode bloquear"):
                validate(dashboard, runtime)


if __name__ == "__main__":
    unittest.main()
