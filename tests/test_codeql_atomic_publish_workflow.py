import unittest
from pathlib import Path


WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "security-specialized-scanners.yml"
)


class CodeQLAtomicPublishWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def section(self, start: str, end: str) -> str:
        after_start = self.text.split(start, 1)[1]
        return after_start.split(end, 1)[0]

    def test_scope_router_keeps_secret_scan_global_and_splits_code_from_dependencies(self):
        scope = self.section("  scope:\n", "  gitleaks:\n")
        self.assertIn("github.rest.pulls.listFiles", scope)
        for output in (
            "python", "node", "python_deps", "node_deps", "sbom", "codeql", "codeql_languages",
        ):
            self.assertIn(f"core.setOutput('{output}'", scope)
        self.assertIn("const codeqlLanguages = (python || node)", scope)
        self.assertIn("? ['javascript-typescript', 'python']", scope)
        self.assertIn(": [];", scope)

        gitleaks = self.section("  gitleaks:\n", "  python-dependency-audit:\n")
        self.assertNotIn("needs: scope", gitleaks)

        python_audit = self.section("  python-dependency-audit:\n", "  npm-audit:\n")
        self.assertIn("if: needs.scope.outputs.python_deps == 'true'", python_audit)
        npm_audit = self.section("  npm-audit:\n", "  sbom:\n")
        self.assertIn("if: needs.scope.outputs.node_deps == 'true'", npm_audit)
        sbom = self.section("  sbom:\n", "  codeql-generate:\n")
        self.assertIn("if: needs.scope.outputs.sbom == 'true'", sbom)
        codeql_generate = self.section("  codeql-generate:\n", "  codeql:\n")
        self.assertIn("if: needs.scope.outputs.codeql == 'true'", codeql_generate)

    def test_language_jobs_use_baseline_parity_matrix_for_code_changes(self):
        section = self.section("  codeql-generate:\n", "  codeql:\n")
        self.assertIn("language: ${{ fromJSON(needs.scope.outputs.codeql_languages) }}", section)
        self.assertIn('category: "/language:${{ matrix.language }}"', section)
        self.assertIn("upload: never", section)

    def test_atomic_publisher_waits_for_selected_language_jobs(self):
        section = self.section("  codeql-generate:\n", "  security-executive-summary:\n")
        self.assertIn("needs: [scope, codeql-generate]", section)
        self.assertIn("needs.scope.outputs.codeql == 'true'", section)
        self.assertIn("CODEQL_LANGUAGES_JSON", section)
        self.assertIn("pattern: codeql-sarif-*", section)
        self.assertEqual(
            section.count(
                "uses: github/codeql-action/upload-sarif@2892aa5e19bbd11bc0cff5427e3b750a04d9e3c2"
            ),
            1,
        )
        self.assertIn("wait-for-processing: true", section)

    def test_atomic_publisher_requires_exact_selected_categories(self):
        section = self.section("  codeql-generate:\n", "  security-executive-summary:\n")
        self.assertIn("python scripts/codeql_category_bridge.py", section)
        self.assertIn('--languages-json "$CODEQL_LANGUAGES_JSON"', section)
        self.assertIn("artifacts/security-scanners/codeql-category-compat/receipt.json", section)
        self.assertIn("wait-for-processing: true", section)
        self.assertNotIn("shutil.copy2(sarif", section)

    def test_push_main_and_manual_keep_full_scan(self):
        scope = self.section("  scope:\n", "  gitleaks:\n")
        self.assertIn("if (context.eventName !== 'pull_request')", scope)
        self.assertIn("core.setOutput('python_deps', 'true')", scope)
        self.assertIn("core.setOutput('node_deps', 'true')", scope)
        self.assertIn("core.setOutput('sbom', 'true')", scope)
        self.assertIn("JSON.stringify(['javascript-typescript', 'python'])", scope)

    def test_codeql_baseline_parity_and_negative_non_source_control(self):
        scope = self.section("  scope:\n", "  gitleaks:\n")
        # A regressão original analisava só Python em PRs Python-only.
        # A matriz deve ser completa para qualquer mudança de código.
        selection = scope.split("const codeqlLanguages = ", 1)[1].split(
            "const codeql =", 1
        )[0]
        self.assertIn("(python || node)", selection)
        self.assertIn("? ['javascript-typescript', 'python']", selection)
        # Documentação sem alteração de código não ativa CodeQL sem necessidade.
        self.assertIn(": [];", selection)
        self.assertIn("const codeql = codeqlLanguages.length > 0", scope)
        # Não alterar nem contornar os controles especializados.
        self.assertIn("const sbom = pythonDeps || nodeDeps", scope)
        self.assertIn("core.setOutput('python_deps', String(pythonDeps))", scope)
        self.assertIn("core.setOutput('node_deps', String(nodeDeps))", scope)

    def test_executive_summary_waits_for_atomic_publish(self):
        section = self.text.split("  security-executive-summary:\n", 1)[1]
        needs = section.split("    if: always()", 1)[0]
        self.assertIn("- scope", needs)
        self.assertIn("- codeql", needs)
        self.assertNotIn("- codeql-generate", needs)
        self.assertIn("if: needs.scope.result != 'success'", section)

    def test_summary_reports_selected_languages(self):
        section = self.section("  codeql-generate:\n", "  security-executive-summary:\n")
        self.assertIn("Configurações CodeQL analisadas:", section)
        self.assertIn("conjunto completo de linguagens do baseline main", section)


if __name__ == "__main__":
    unittest.main()
