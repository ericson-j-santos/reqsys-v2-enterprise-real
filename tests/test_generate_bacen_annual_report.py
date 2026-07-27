import unittest

from scripts.generate_bacen_annual_report import (
    parse_designation,
    regenerate,
    render_controls_block,
    render_executive_block,
)

MATRIX = """
controls:
  - id: BACEN-01
    domain: governance
    criticality: critical
    status: partial
  - id: BACEN-02
    domain: identity
    criticality: high
    status: implemented
  - id: BACEN-03
    domain: third_party
    criticality: high
    status: gap
"""

PENDING_DESIGNATION = """
designation:
  status: pending_formal_designation
  executive_name: null
  executive_role: null
"""

DESIGNATED = """
designation:
  status: designated
  executive_name: Fulana de Tal
  executive_role: Diretora de Riscos
  designated_at: "2026-01-10"
  designation_document_reference: "Ata 12/2026"
"""

REPORT_TEMPLATE = """# Report

<!-- BACEN-08:EXECUTIVE:START -->
placeholder
<!-- BACEN-08:EXECUTIVE:END -->

<!-- BACEN-08:CONTROLS-SUMMARY:START -->
placeholder
<!-- BACEN-08:CONTROLS-SUMMARY:END -->
"""


class ParseDesignationTests(unittest.TestCase):
    def test_parses_pending_designation(self):
        fields = parse_designation(PENDING_DESIGNATION)
        self.assertEqual(fields["status"], "pending_formal_designation")
        self.assertEqual(fields["executive_name"], "null")

    def test_parses_designated(self):
        fields = parse_designation(DESIGNATED)
        self.assertEqual(fields["status"], "designated")
        self.assertEqual(fields["executive_name"], "Fulana de Tal")
        self.assertEqual(fields["designation_document_reference"], "Ata 12/2026")


class RenderExecutiveBlockTests(unittest.TestCase):
    def test_pending_designation_never_invents_a_name(self):
        block = render_executive_block(parse_designation(PENDING_DESIGNATION))
        self.assertIn("pendente de designação formal", block)
        self.assertNotIn("Fulana", block)

    def test_designated_renders_real_fields(self):
        block = render_executive_block(parse_designation(DESIGNATED))
        self.assertIn("Fulana de Tal", block)
        self.assertIn("Diretora de Riscos", block)
        self.assertIn("Ata 12/2026", block)


class RenderControlsBlockTests(unittest.TestCase):
    def test_summarizes_real_counts(self):
        from scripts.validate_bacen_controls import parse_controls

        block = render_controls_block(parse_controls(MATRIX))
        self.assertIn("BACEN-01", block)
        self.assertIn("Implementados: **1**", block)
        self.assertIn("Lacunas: **1**", block)

    def test_is_deterministic(self):
        from scripts.validate_bacen_controls import parse_controls

        controls = parse_controls(MATRIX)
        self.assertEqual(render_controls_block(controls), render_controls_block(controls))


class RegenerateTests(unittest.TestCase):
    def test_replaces_both_blocks_and_is_idempotent(self):
        once = regenerate(REPORT_TEMPLATE, MATRIX, PENDING_DESIGNATION)
        twice = regenerate(once, MATRIX, PENDING_DESIGNATION)
        self.assertEqual(once, twice)
        self.assertNotIn("placeholder", once)
        self.assertIn("BACEN-01", once)


if __name__ == "__main__":
    unittest.main()
