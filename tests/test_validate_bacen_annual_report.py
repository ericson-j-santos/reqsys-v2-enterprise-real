import unittest

from scripts.validate_bacen_annual_report import validate

DESIGNATION_PENDING = """
designation:
  status: pending_formal_designation
  executive_name: null
"""

DESIGNATION_DESIGNATED = """
designation:
  status: designated
  executive_name: Fulana de Tal
"""

DESIGNATION_INVALID = """
designation:
  status: made_up_status
"""

REPORT_GENERATED = """# Report

<!-- BACEN-08:EXECUTIVE:START -->
- Nome: Fulana de Tal
<!-- BACEN-08:EXECUTIVE:END -->

## Resumo executivo

Texto real preenchido pela equipe de governança, sem placeholder.

<!-- BACEN-08:CONTROLS-SUMMARY:START -->
| BACEN-01 | governance | critical | implemented |
<!-- BACEN-08:CONTROLS-SUMMARY:END -->
"""

REPORT_NEVER_GENERATED = """# Report

<!-- BACEN-08:EXECUTIVE:START -->
<!-- BACEN-08:EXECUTIVE:END -->

<!-- BACEN-08:CONTROLS-SUMMARY:START -->
*(executar o gerador para preencher)*
<!-- BACEN-08:CONTROLS-SUMMARY:END -->
"""

REPORT_WITH_NARRATIVE_PLACEHOLDER = """# Report

<!-- BACEN-08:EXECUTIVE:START -->
<!-- BACEN-08:EXECUTIVE:END -->

## Resumo executivo

*(seção narrativa — preencher)*

<!-- BACEN-08:CONTROLS-SUMMARY:START -->
| BACEN-01 | governance | critical | implemented |
<!-- BACEN-08:CONTROLS-SUMMARY:END -->
"""


class ValidateTests(unittest.TestCase):
    def test_valid_report_with_designated_executive(self):
        report = validate(REPORT_GENERATED, DESIGNATION_DESIGNATED)
        self.assertEqual(report["result"], "valid")
        self.assertEqual(report["errors"], [])

    def test_pending_designation_is_a_warning_not_an_error(self):
        report = validate(REPORT_GENERATED, DESIGNATION_PENDING)
        self.assertEqual(report["result"], "valid_with_pending_items")
        self.assertEqual(report["errors"], [])
        self.assertTrue(any("designado formalmente" in w for w in report["warnings"]))

    def test_never_generated_report_is_invalid(self):
        report = validate(REPORT_NEVER_GENERATED, DESIGNATION_PENDING)
        self.assertEqual(report["result"], "invalid")

    def test_invalid_designation_status_is_an_error(self):
        report = validate(REPORT_GENERATED, DESIGNATION_INVALID)
        self.assertEqual(report["result"], "invalid")

    def test_narrative_placeholder_is_flagged_as_warning(self):
        report = validate(REPORT_WITH_NARRATIVE_PLACEHOLDER, DESIGNATION_DESIGNATED)
        self.assertGreaterEqual(report["summary"]["narrative_sections_pending"], 1)


if __name__ == "__main__":
    unittest.main()
