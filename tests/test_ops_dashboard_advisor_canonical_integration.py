import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.inject_workflow_efficiency_visual_card import (
    hydrate_advisor_contract,
    patch_dashboard,
)
from scripts.validate_executive_promotion_advisor_card import validate


MINIMAL_HTML = '''<!doctype html>
<html><body><main>
  <section class="card"><h2>Runtime público — readiness Fly/DuckDNS</h2></section>
</main><script>
function statusClass(value) { return value; }
function addLink() {}
async function renderRuntimeExecutiveIndex() {
  const payload = {cards:{}};
  const cards = payload.cards || fallback.cards;
}
</script></body></html>
'''


class OpsDashboardAdvisorCanonicalIntegrationTests(unittest.TestCase):
    def write_runtime(self, root: Path) -> Path:
        path = root / "runtime-executive-index.json"
        path.write_text(json.dumps({"cards": {}, "links": {}, "guardrails": []}), encoding="utf-8")
        return path

    def test_safe_fallback_is_report_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = self.write_runtime(root)
            with patch("scripts.inject_workflow_efficiency_visual_card.ADVISOR_CANDIDATES", ()):
                source = hydrate_advisor_contract(runtime)
            payload = json.loads(runtime.read_text(encoding="utf-8"))
            card = payload["cards"]["executive_promotion_advisor"]
            self.assertEqual(source, "safe-fallback")
            self.assertEqual(card["decision"], "REVIEW")
            self.assertFalse(card["production_blocker"])
            self.assertTrue(card["human_approval_required"])

    def test_real_evidence_has_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = self.write_runtime(root)
            evidence = root / "advisor.json"
            evidence.write_text(json.dumps({
                "decision": "READY",
                "confidence_percent": 98,
                "risk_domains": [],
                "recommendation": "Promover com aprovação humana.",
            }), encoding="utf-8")
            with patch("scripts.inject_workflow_efficiency_visual_card.ADVISOR_CANDIDATES", (evidence,)):
                source = hydrate_advisor_contract(runtime)
            card = json.loads(runtime.read_text(encoding="utf-8"))["cards"]["executive_promotion_advisor"]
            self.assertEqual(source, str(evidence))
            self.assertEqual(card["decision"], "READY")
            self.assertFalse(card["production_blocker"])
            self.assertTrue(card["human_approval_required"])

    def test_dashboard_injection_is_idempotent_and_validated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dashboard = root / "index.html"
            runtime = self.write_runtime(root)
            dashboard.write_text(MINIMAL_HTML, encoding="utf-8")
            with patch("scripts.inject_workflow_efficiency_visual_card.ADVISOR_CANDIDATES", ()):
                hydrate_advisor_contract(runtime)
            patch_dashboard(dashboard)
            patch_dashboard(dashboard)
            result = validate(dashboard, runtime)
            html = dashboard.read_text(encoding="utf-8")
            self.assertEqual(html.count('id="executive-promotion-advisor-card"'), 1)
            self.assertEqual(html.count('id="workflow-efficiency-visual-card"'), 1)
            self.assertTrue(result["contract_validated"])


if __name__ == "__main__":
    unittest.main()
