import json
import unittest

from scripts.build_runtime_environment_evidence import append_ledger, build_record


class RuntimeEnvironmentEvidenceTests(unittest.TestCase):
    def evidence(self):
        return {
            "contract": "fly-environment-homologation-gate",
            "ok": True,
            "environment": "stg",
            "expected_sha": "abcdef1234567890",
            "observed_sha": "abcdef123456",
            "correlation_id": "corr-1",
            "base_url": "https://reqsys-api-stg.fly.dev",
            "fly_app": "reqsys-api-stg",
            "generated_at_epoch": 1784145600,
            "probes": [{"name": "health", "ok": True}],
            "blocking_issues": [],
        }

    def build(self, evidence=None, run_id="123"):
        payload = evidence or self.evidence()
        raw = (json.dumps(payload, sort_keys=True) + "\n").encode()
        return build_record(
            payload,
            evidence_bytes=raw,
            source_run_id=run_id,
            source_head_sha="abcdef1234567890",
            source_workflow="Fly Environment Homologation Gate",
        )

    def test_builds_runtime_record_with_digest(self):
        record = self.build()
        self.assertEqual(record["evidence_source"], "runtime")
        self.assertEqual(record["environment"], "stg")
        self.assertEqual(len(record["evidence_sha256"]), 64)
        self.assertEqual(record["attestation_provider"], "github-artifact-attestations")
        self.assertFalse(record["production_blocker"])

    def test_prod_requires_human_approval(self):
        evidence = self.evidence()
        evidence["environment"] = "prod"
        record = self.build(evidence)
        self.assertTrue(record["human_approval_required"])

    def test_rejects_failed_homologation(self):
        evidence = self.evidence()
        evidence["ok"] = False
        with self.assertRaises(ValueError):
            self.build(evidence)

    def test_rejects_sha_mismatch(self):
        evidence = self.evidence()
        evidence["observed_sha"] = "999999999999"
        with self.assertRaises(ValueError):
            self.build(evidence)

    def test_ledger_is_idempotent_by_run_and_environment(self):
        first = self.build(run_id="123")
        replacement = dict(first, evidence_sha256="f" * 64)
        ledger = append_ledger([first], replacement)
        self.assertEqual(len(ledger), 1)
        self.assertEqual(ledger[0]["evidence_sha256"], "f" * 64)


if __name__ == "__main__":
    unittest.main()
