import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.validate_bacen_third_party_register import env_vars, parse_providers, validate

VALID_REGISTER = """
schema_version: 1.0.0
control_id: BACEN-05
providers:
  - id: BACEN-05-T01
    provider: Example Cloud
    category: identity
    purpose: Login federado
    config_source:
      - EXAMPLE_CLIENT_ID
      - EXAMPLE_CLIENT_SECRET
    data_classification: identity_claims
    criticality: critical
    risk_review_status: pending_formal_review
    dpa_status: pending_verification
"""

VALID_ENV = "EXAMPLE_CLIENT_ID=\nEXAMPLE_CLIENT_SECRET=\n# comment\nLOCAL_ONLY_VAR=x\n"


class ParseProvidersTests(unittest.TestCase):
    def test_parses_scalar_and_list_fields(self):
        providers = parse_providers(VALID_REGISTER)
        self.assertEqual(len(providers), 1)
        provider = providers[0]
        self.assertEqual(provider["id"], "BACEN-05-T01")
        self.assertEqual(provider["criticality"], "critical")
        self.assertEqual(provider["config_source"], ["EXAMPLE_CLIENT_ID", "EXAMPLE_CLIENT_SECRET"])


class EnvVarsTests(unittest.TestCase):
    def test_ignores_comments_and_blank_lines(self):
        names = env_vars("# comment\n\nFOO=bar\nBAZ=\n")
        self.assertEqual(names, {"FOO", "BAZ"})


class ValidateTests(unittest.TestCase):
    def test_valid_register_with_matching_env(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            register_path = root / "register.yaml"
            env_path = root / ".env.example"
            register_path.write_text(VALID_REGISTER, encoding="utf-8")
            env_path.write_text(VALID_ENV, encoding="utf-8")

            report = validate(root, register_path, env_path)

            self.assertEqual(report["result"], "valid")
            self.assertEqual(report["errors"], [])
            self.assertFalse(report["summary"]["drift_detected"])

    def test_detects_undeclared_external_variable(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            register_path = root / "register.yaml"
            env_path = root / ".env.example"
            register_path.write_text(VALID_REGISTER, encoding="utf-8")
            env_path.write_text(VALID_ENV + "AZURE_NEW_INTEGRATION_KEY=\n", encoding="utf-8")

            report = validate(root, register_path, env_path)

            self.assertEqual(report["result"], "invalid")
            self.assertTrue(any("AZURE_NEW_INTEGRATION_KEY" in error for error in report["errors"]))
            self.assertTrue(report["summary"]["drift_detected"])

    def test_detects_reference_to_missing_env_var(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            register_path = root / "register.yaml"
            env_path = root / ".env.example"
            register_path.write_text(VALID_REGISTER, encoding="utf-8")
            env_path.write_text("EXAMPLE_CLIENT_ID=\n", encoding="utf-8")

            report = validate(root, register_path, env_path)

            self.assertEqual(report["result"], "invalid")
            self.assertTrue(
                any("EXAMPLE_CLIENT_SECRET" in error for error in report["errors"])
            )


if __name__ == "__main__":
    unittest.main()
