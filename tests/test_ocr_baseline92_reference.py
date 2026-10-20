"""Regression tests for the isolated Baseline92 standalone reference gate."""
from __future__ import annotations

import copy
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "tests" / "ocr_baseline92_reference.py"
SPEC = importlib.util.spec_from_file_location("ocr_baseline92_reference", RUNNER_PATH)
if SPEC is None or SPEC.loader is None:  # pragma: no cover - import precondition
    raise RuntimeError("reference_runner_import_failed")
reference = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = reference
SPEC.loader.exec_module(reference)

FIXTURE = ROOT / "tests" / "fixtures" / "ocr_baseline92_reference"
ATTESTATION = FIXTURE / "source-attestation.json"
INVENTORY = ROOT / "audit" / "ocr-baseline92" / "inventory.json"
PUBLIC_GENERATOR = FIXTURE / "gerar_ocr_evidencia_v1_0_0.py"


def private_generator_path() -> Path:
    value = os.environ.get("OCR_BASELINE92_REFERENCE_GENERATOR", "").strip()
    if not value:
        if os.environ.get("OCR_BASELINE92_REQUIRE_PRIVATE_SOURCE") == "1":
            raise RuntimeError("private_reference_generator_required")
        raise unittest.SkipTest("private Baseline92 source not provided")
    requested_path = Path(value)
    if requested_path.is_symlink():
        raise RuntimeError("private_reference_generator_invalid")
    path = requested_path.resolve()
    if not path.is_file():
        raise RuntimeError("private_reference_generator_invalid")
    return path


class Baseline92ReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if PUBLIC_GENERATOR.exists():
            raise RuntimeError("private_reference_leaked_into_public_repository")
        cls.generator = private_generator_path()
        cls.attestation, _ = reference.load_attestation(ATTESTATION)
        cls.inventory, cls.expected_ids, _ = reference.load_inventory(INVENTORY)
        cls.parsed = reference.parse_reference(cls.generator, cls.attestation)
        cls.report = reference.build_reference_report(cls.generator, ATTESTATION, INVENTORY)

    def test_original_generator_payload_and_inventory_are_exact(self) -> None:
        self.assertEqual(reference.sha256_bytes(self.generator.read_bytes()), reference.GENERATOR_SHA256)
        self.assertEqual(reference.sha256_bytes(ATTESTATION.read_bytes()), reference.ATTESTATION_SHA256)
        self.assertEqual(reference.sha256_bytes(INVENTORY.read_bytes()), reference.INVENTORY_SHA256)
        self.assertEqual(reference.sha256_bytes(self.parsed.payload), reference.PAYLOAD_SHA256)
        self.assertEqual(len(self.parsed.manifest), 24)
        self.assertEqual(reference._ids_from_sources(self.parsed.files), self.expected_ids)

    def test_executes_every_body_twice_without_non_pass_outcomes(self) -> None:
        self.assertEqual(
            self.report["execution_summary"],
            {
                "bodies_executed_per_run": 92,
                "bodies_passed_per_run": 92,
                "cases_per_run": 92,
                "replays": 2,
                "total_body_invocations": 184,
            },
        )
        for execution in self.report["executions"].values():
            self.assertEqual(execution["tests_run"], 92)
            self.assertEqual(execution["passed"], 92)
            self.assertTrue(all(case["body_executed"] for case in execution["cases"]))
            self.assertTrue(all(case["outcome"] == "PASSED" for case in execution["cases"]))

    def test_certifies_reference_without_certifying_current_engine(self) -> None:
        self.assertTrue(self.report["original_v1_0_generator_and_payload_bytes_verified"])
        self.assertFalse(self.report["original_archive_bytes_reverified_in_this_run"])
        self.assertTrue(self.report["reference_standalone_functional_certified"])
        self.assertFalse(self.report["current_engine_baseline_functional_certified"])
        self.assertEqual(self.report["current_engine_status"], "BLOCKED_API_COMPATIBILITY")
        self.assertEqual(self.report["semantic_equivalence_to_current_engine"], "NOT_PROVEN")
        self.assertFalse(self.report["legacy_modules_integrated"])

    def test_negative_controls_are_complete_and_revalidated(self) -> None:
        controls = self.report["negative_controls_passed"]
        self.assertEqual(len(controls), 11)
        self.assertEqual(len(controls), len(set(controls)))
        reference.validate_final_report(self.report, self.expected_ids)

        invalid_report = copy.deepcopy(self.report)
        invalid_report["negative_controls_passed"] = [f"invented_control_{index}" for index in range(11)]
        with self.assertRaisesRegex(reference.ReferenceError, "report_negative_controls_incomplete"):
            reference.validate_final_report(invalid_report, self.expected_ids)

    def test_tampered_generator_is_rejected_before_payload_use(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "generator.py"
            raw = bytearray(self.generator.read_bytes())
            raw[-1] ^= 1
            tampered.write_bytes(raw)
            with self.assertRaisesRegex(reference.ReferenceError, "generator_bytes_changed"):
                reference.parse_reference(tampered, self.attestation)

    def test_path_traversal_is_rejected(self) -> None:
        for unsafe in ("../escape.py", "/absolute.py", "a\\b.py", "a//b.py"):
            with self.subTest(path=unsafe):
                with self.assertRaises(reference.ReferenceError):
                    reference._safe_payload_path(unsafe)

    def test_false_current_engine_certification_is_rejected(self) -> None:
        invalid_attestation = copy.deepcopy(self.attestation)
        invalid_attestation["claims"]["current_engine_baseline_functional_certified"] = True
        with self.assertRaisesRegex(reference.ReferenceError, "false_current_engine_certification"):
            reference.validate_attestation(invalid_attestation)

        invalid_report = copy.deepcopy(self.report)
        invalid_report["current_engine_baseline_functional_certified"] = True
        with self.assertRaisesRegex(reference.ReferenceError, "report_false_current_certification"):
            reference.validate_final_report(invalid_report, self.expected_ids)

    def test_private_source_identity_tampering_is_rejected(self) -> None:
        mutations = {
            "repository": "ericson-j-santos/another-private-repository",
            "commit_sha": "0" * 40,
            "path": "audit/baseline92/v1.0/other.py",
        }
        for field, value in mutations.items():
            with self.subTest(field=field):
                invalid_attestation = copy.deepcopy(self.attestation)
                invalid_attestation["source"]["generator"][field] = value
                with self.assertRaises(reference.ReferenceError):
                    reference.validate_attestation(invalid_attestation)


if __name__ == "__main__":
    unittest.main()
