"""Gates sem bypass: o CI executa testes reais sem baixar dependências de apt.

Falhas de DNS do GitHub-hosted runner não são falhas de código de produto.
Alterar dependência de instalação mantém assertivas, não converte falha em skipped.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class HostedRunnerOfflinePrerequisites(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        cls.gold = (ROOT / ".github/workflows/golden-test-advanced.yml").read_text(encoding="utf-8")
        cls.ux = (ROOT / ".github/workflows/ux-evidence-smoke.yml").read_text(encoding="utf-8")
        cls.e2e = (ROOT / ".github/workflows/ci-e2e-governado.yml").read_text(encoding="utf-8")
        cls.play = (ROOT / "frontend/playwright.config.js").read_text(encoding="utf-8")

    def test_binary_pyodbc_is_pinned_and_imported(self):
        self.assertIn("--only-binary=:all: 'pyodbc==5.2.0'", self.ci)
        self.assertIn("import pyodbc", self.ci)
        self.assertIn("pyodbc.drivers()", self.ci)
        self.assertIn("ODBC_MANAGER_INVALID", self.ci)
        self.assertNotIn("apt-get", self.ci)

    def test_all_visual_workflows_use_system_chrome_fail_closed(self):
        for text in (self.ci, self.gold, self.ux, self.e2e):
            self.assertIn("CHROME_PREINSTALLED_MISSING", text)
            self.assertIn('REQSYS_SYSTEM_CHROME=1', text)
            self.assertNotIn("playwright install --with-deps", text)
            self.assertIn("playwright test", text)

    def test_playwright_config_only_switches_channel_when_opted_in(self):
        self.assertIn("process.env.REQSYS_SYSTEM_CHROME === '1'", self.play)
        self.assertIn("...(systemChrome ? { channel: 'chrome' } : {})", self.play)
        self.assertIn("trace: 'on-first-retry'", self.play)

    def test_existing_backend_and_frontend_tests_not_bypassed(self):
        self.assertIn("python -m pytest tests/ -v --tb=short", self.ci)
        self.assertIn("--cov-fail-under=60", self.ci)
        self.assertIn("npx playwright test tests/e2e/accessibility-visual.spec.ts", self.gold)
        self.assertIn("npx playwright test tests/e2e/ux-evidence.spec.js", self.ux)
        self.assertIn("npx playwright test", self.e2e)
        self.assertIn("tests/e2e/navigation-integrity.spec.js", self.e2e)
        self.assertNotIn("continue-on-error: true", self.ux)
        # A auditoria WCAG formal mantém uma exceção pré-existente e explícita.
        # O teste E2E real não pode ser silenciado por continue-on-error.
        e2e_step = self.e2e.split("      - name: Executar E2E governado", 1)[1].split(
            "      - name: Validar evidência automatizada WCAG 2.2", 1
        )[0]
        self.assertNotIn("continue-on-error:", e2e_step)
        self.assertNotIn("continue-on-error: true", self.gold)

    def test_test_of_test_detects_removed_chrome_guard(self):
        altered = self.gold.replace("CHROME_PREINSTALLED_MISSING", "CHROME_IGNORED")
        with self.assertRaises(AssertionError):
            self.assertIn("CHROME_PREINSTALLED_MISSING", altered)


if __name__ == "__main__":
    unittest.main()
