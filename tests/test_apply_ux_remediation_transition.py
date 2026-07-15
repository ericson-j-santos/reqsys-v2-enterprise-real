import unittest

from scripts.apply_ux_remediation_transition import apply_transition, sign_evidence


class GovernedTransitionTests(unittest.TestCase):
    def setUp(self):
        self.history = [{"id": "100:recovery_rate_drop", "state": "open", "source_run_id": "100"}]

    def test_allows_open_to_in_progress(self):
        updated, audit = apply_transition(
            self.history,
            {"remediation_id": "100:recovery_rate_drop", "target_state": "in_progress", "actor": "UX_UI"},
            secret="secret",
        )
        self.assertEqual(updated[0]["state"], "in_progress")
        self.assertEqual(audit["from_state"], "open")

    def test_rejects_invalid_transition(self):
        with self.assertRaises(ValueError):
            apply_transition(
                self.history,
                {"remediation_id": "100:recovery_rate_drop", "target_state": "resolved", "actor": "UX_UI"},
                secret="secret",
                qualified_evidence={"ux_100_ready": True, "source_run_id": "101"},
            )

    def test_resolves_only_with_signed_new_qualified_evidence(self):
        history = [{"id": "100:a", "state": "in_progress", "source_run_id": "100"}]
        evidence = {"summary": "CTA corrigido", "artifact_sha256": "abc123"}
        signature = sign_evidence(evidence, "secret")
        updated, audit = apply_transition(
            history,
            {
                "remediation_id": "100:a",
                "target_state": "resolved",
                "actor": "QA_GOVERNANCA",
                "resolution_evidence": evidence,
                "signature": signature,
            },
            secret="secret",
            qualified_evidence={"ux_100_ready": True, "source_run_id": "101"},
        )
        self.assertEqual(updated[0]["state"], "resolved")
        self.assertTrue(audit["signed_resolution"])
        self.assertEqual(updated[0]["qualified_resolution_run_id"], "101")

    def test_rejects_invalid_signature_or_same_run(self):
        history = [{"id": "100:a", "state": "in_progress", "source_run_id": "100"}]
        request = {
            "remediation_id": "100:a",
            "target_state": "resolved",
            "actor": "QA_GOVERNANCA",
            "resolution_evidence": {"summary": "ok"},
            "signature": "invalid",
        }
        with self.assertRaises(ValueError):
            apply_transition(
                history,
                request,
                secret="secret",
                qualified_evidence={"ux_100_ready": True, "source_run_id": "100"},
            )


if __name__ == "__main__":
    unittest.main()
