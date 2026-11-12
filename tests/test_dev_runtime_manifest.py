"""Validação do manifesto PC24x7 e controles negativos, sem rede."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_dev_runtime_manifest import MANIFEST, check_manifest, evaluate


class TestStaticDevManifest(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_current_manifest_valid_but_not_physical(self):
        self.assertEqual(check_manifest(self.data), [])
        report = evaluate()
        self.assertEqual(report["status"], "passed_with_warnings")
        self.assertEqual(report["summary"]["operational_status"], "config_only")
        self.assertFalse(report["summary"]["physical_e2e_verified"])
        self.assertFalse(report["summary"]["signed_locator_verified"])
        self.assertFalse(report["summary"]["http_probe_performed"])

    def test_unsigned_locator_blocked(self):
        data = copy.deepcopy(self.data)
        data["runtime_discovery"]["dev"]["locator_channel"] = ""
        self.assertIn("dev_locator_channel_unexpected", check_manifest(data))

    def test_non_pc24x7_target_blocked(self):
        data = copy.deepcopy(self.data)
        data["runtime_discovery"]["dev"]["runtime_target"] = "flyio"
        self.assertIn("dev_runtime_target_unexpected", check_manifest(data))

    def test_external_gateway_blocked(self):
        data = copy.deepcopy(self.data)
        data["runtime_discovery"]["dev"]["gateway"] = "http://0.0.0.0:8083"
        self.assertIn("dev_gateway_unexpected", check_manifest(data))

    def test_fly_dev_public_url_blocked(self):
        data = copy.deepcopy(self.data)
        data["targets"][0]["url"] = "https://old.fly.dev/"
        self.assertIn("insecure_or_retired_provider_url", check_manifest(data))

    def test_hml_promotion_blocked(self):
        data = copy.deepcopy(self.data)
        data["runtime_discovery"]["hml"]["runtime_target"] = "pc24x7"
        self.assertIn("hml_must_remain_not_promoted", check_manifest(data))

    def test_insecure_scheme_blocked(self):
        data = copy.deepcopy(self.data)
        data["targets"][0]["url"] = "http://unsafe.example/"
        self.assertIn("insecure_or_retired_provider_url", check_manifest(data))

    def test_invalid_and_missing_json_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "manifest.json"
            self.assertEqual(evaluate(path)["status"], "failed")
            path.write_text("{", encoding="utf-8")
            self.assertEqual(evaluate(path)["status"], "failed")

    def test_duplicate_dev_entrypoint_blocked(self):
        data = copy.deepcopy(self.data)
        data["targets"].append(copy.deepcopy(data["targets"][0]))
        self.assertIn("dev_entrypoint_count_invalid", check_manifest(data))

    def test_environment_promoted_by_lifecycle_blocked(self):
        data = copy.deepcopy(self.data)
        data["targets"][1]["lifecycle"] = "active"
        self.assertIn("environment_promotion_not_allowed", check_manifest(data))


if __name__ == "__main__":
    unittest.main()
