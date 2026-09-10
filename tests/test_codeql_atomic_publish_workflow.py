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

    def test_language_jobs_generate_without_incremental_publish(self):
        section = self.section("  codeql:\n", "  codeql-publish:\n")
        self.assertIn("- javascript-typescript", section)
        self.assertIn("- python", section)
        self.assertIn('category: "/language:${{ matrix.language }}"', section)
        self.assertIn("upload: never", section)
        self.assertNotIn("upload: always", section)

    def test_atomic_publisher_waits_for_both_language_jobs(self):
        section = self.section("  codeql-publish:\n", "  security-executive-summary:\n")
        self.assertIn("needs: codeql", section)
        self.assertIn("pattern: codeql-sarif-*", section)
        self.assertEqual(
            section.count("uses: github/codeql-action/upload-sarif@v4"),
            1,
        )
        self.assertIn(
            "sarif_file: artifacts/security-scanners/codeql-publish",
            section,
        )
        self.assertIn("wait-for-processing: true", section)

    def test_atomic_publisher_requires_exact_baseline_categories(self):
        section = self.section("  codeql-publish:\n", "  security-executive-summary:\n")
        self.assertIn('"/language:javascript-typescript/"', section)
        self.assertIn('"/language:python/"', section)
        self.assertIn("Configurações CodeQL ausentes", section)
        self.assertIn("Categoria CodeQL duplicada", section)

    def test_executive_summary_waits_for_atomic_publish(self):
        section = self.text.split("  security-executive-summary:\n", 1)[1]
        needs = section.split("    if: always()", 1)[0]
        self.assertIn("- codeql-publish", needs)
        self.assertNotIn("- codeql\n", needs)

    def test_summary_backticks_are_escaped_for_bash(self):
        section = self.section("  codeql:\n", "  security-executive-summary:\n")
        self.assertNotIn('echo "As configurações `javascript-typescript`', section)
        self.assertIn("\\`javascript-typescript\\`", section)
        self.assertIn("\\`python\\`", section)


if __name__ == "__main__":
    unittest.main()
