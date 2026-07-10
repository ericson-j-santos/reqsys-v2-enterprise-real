import tempfile
import unittest
from pathlib import Path

from scripts.inject_workflow_efficiency_visual_card import patch_dashboard


BASE_HTML = '''<!doctype html>
<html><body>
<main>
    <section class="card">
      <h2>Runtime público — readiness Fly/DuckDNS</h2>
    </section>
</main>
<script>
    function statusClass(value) { return value || 'unknown'; }
    function addLink(container, label, href) { container.innerHTML += label + href; }
    async function renderRuntimeExecutiveIndex() {
      const payload = { cards: {}, links: {} };
      const fallback = { cards: {} };
      const cards = payload.cards || fallback.cards;
      return cards;
    }
</script>
</body></html>
'''


class WorkflowEfficiencyVisualCardTests(unittest.TestCase):
    def test_injects_card_function_and_hook(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "index.html"
            path.write_text(BASE_HTML, encoding="utf-8")

            patch_dashboard(path)
            html = path.read_text(encoding="utf-8")

            self.assertIn('id="workflow-efficiency-visual-card"', html)
            self.assertIn("function renderWorkflowEfficiency(payload)", html)
            self.assertIn("renderWorkflowEfficiency(payload);", html)
            self.assertIn("payload?.cards?.workflow_efficiency", html)

    def test_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "index.html"
            path.write_text(BASE_HTML, encoding="utf-8")

            patch_dashboard(path)
            first = path.read_text(encoding="utf-8")
            patch_dashboard(path)
            second = path.read_text(encoding="utf-8")

            self.assertEqual(first, second)
            self.assertEqual(second.count('id="workflow-efficiency-visual-card"'), 1)
            self.assertEqual(second.count("function renderWorkflowEfficiency(payload)"), 1)


if __name__ == "__main__":
    unittest.main()
