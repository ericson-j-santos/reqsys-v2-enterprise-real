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

## Baseline normativa utilizada

- `as_of`: `2026-09-02T22:01:00Z`
- Estado: `transitional_pending_normative_axis`

<!-- BACEN-08:EXECUTIVE:START -->
- Nome: Fulana de Tal
<!-- BACEN-08:EXECUTIVE:END -->

## Resumo executivo

Texto real preenchido pela equipe de governança, sem placeholder.

<!-- BACEN-08:CONTROLS-SUMMARY:START -->
| BACEN-01 | governance | critical | implemented |
<!-- BACEN-08:CONTROLS-SUMMARY:END -->

## Incidentes de segurança do período

- Estado: `nao_avaliado`.

## Resultados dos testes de continuidade de negócios

- Estado: `nao_avaliado`.

## Resultados dos testes de intrusão

- Estado: `nao_avaliado`.

## Varreduras e análises de vulnerabilidades

- Estado: `nao_avaliado`.

## Plano de ação para o próximo ciclo

- Estado: `parcial`.
"""

REPORT_WITH_COVERAGE_SCALAR = REPORT_GENERATED.replace(
    "<!-- BACEN-08:CONTROLS-SUMMARY:END -->",
    "Cobertura ponderada: **50.0%**\n<!-- BACEN-08:CONTROLS-SUMMARY:END -->",
)

REPORT_NEVER_GENERATED = REPORT_GENERATED.replace(
    "| BACEN-01 | governance | critical | implemented |",
    "*(executar o gerador para preencher)*",
)

REPORT_WITH_NARRATIVE_PLACEHOLDER = REPORT_GENERATED.replace(
    "Texto real preenchido pela equipe de governança, sem placeholder.",
    "*(seção narrativa — preencher)*",
)

REPORT_MISSING_CONTINUITY = REPORT_GENERATED.replace(
    "## Resultados dos testes de continuidade de negócios\n\n- Estado: `nao_avaliado`.\n\n",
    "",
)

REPORT_EMPTY_PENTEST = REPORT_GENERATED.replace(
    "## Resultados dos testes de intrusão\n\n- Estado: `nao_avaliado`.\n\n",
    "## Resultados dos testes de intrusão\n\n",
)

REPORT_WITHOUT_AS_OF = REPORT_GENERATED.replace(
    "- `as_of`: `2026-09-02T22:01:00Z`\n",
    "",
)


class ValidateTests(unittest.TestCase):
    def test_valid_report_with_designated_executive(self):
        report = validate(REPORT_GENERATED, DESIGNATION_DESIGNATED)
        self.assertEqual(report["result"], "valid")
        self.assertEqual(report["errors"], [])
        self.assertFalse(report["summary"]["coverage_scalar_present"])
        self.assertTrue(report["summary"]["contract_complete"])
        self.assertEqual(report["summary"]["contract_sections_missing"], [])
        self.assertEqual(report["summary"]["contract_sections_empty"], [])
        self.assertEqual(report["summary"]["report_as_of"], "2026-09-02T22:01:00Z")

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

    def test_aggregate_coverage_scalar_is_invalid(self):
        report = validate(REPORT_WITH_COVERAGE_SCALAR, DESIGNATION_DESIGNATED)
        self.assertEqual(report["result"], "invalid")
        self.assertTrue(report["summary"]["coverage_scalar_present"])
        self.assertTrue(any("escalar agregado" in error for error in report["errors"]))

    def test_missing_required_contract_section_is_invalid(self):
        report = validate(REPORT_MISSING_CONTINUITY, DESIGNATION_DESIGNATED)
        self.assertEqual(report["result"], "invalid")
        self.assertIn("continuidade_negocios", report["summary"]["contract_sections_missing"])

    def test_empty_required_contract_section_is_invalid(self):
        report = validate(REPORT_EMPTY_PENTEST, DESIGNATION_DESIGNATED)
        self.assertEqual(report["result"], "invalid")
        self.assertIn("testes_intrusao", report["summary"]["contract_sections_empty"])

    def test_missing_as_of_is_invalid(self):
        report = validate(REPORT_WITHOUT_AS_OF, DESIGNATION_DESIGNATED)
        self.assertEqual(report["result"], "invalid")
        self.assertIsNone(report["summary"]["report_as_of"])
        self.assertTrue(any("as_of" in error for error in report["errors"]))


if __name__ == "__main__":
    unittest.main()
