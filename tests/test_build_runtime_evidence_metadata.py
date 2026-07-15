import unittest

from scripts.build_runtime_evidence_metadata import build_metadata


class RuntimeEvidenceMetadataTests(unittest.TestCase):
    def test_marks_valid_post_merge_smoke_as_runtime(self):
        metadata = build_metadata(
            environment="stg",
            correlation_id="ux-smoke-29440614067",
            merge_sha="a" * 40,
            origin="post-merge-smoke",
            generated_at="2026-07-15T18:50:00+00:00",
        )
        self.assertEqual(metadata["evidence_source"], "runtime")
        self.assertEqual(metadata["verification_status"], "verified")
        self.assertEqual(metadata["validation_errors"], [])
        self.assertFalse(metadata["production_blocker"])
        self.assertTrue(metadata["human_approval_required"])

    def test_rejects_invalid_environment_and_sha(self):
        metadata = build_metadata(
            environment="local",
            correlation_id="short",
            merge_sha="abc",
            origin="manual",
            generated_at="2026-07-15T18:50:00",
        )
        self.assertEqual(metadata["evidence_source"], "unverified")
        self.assertEqual(metadata["verification_status"], "rejected")
        self.assertIn("invalid_environment", metadata["validation_errors"])
        self.assertIn("invalid_origin", metadata["validation_errors"])
        self.assertIn("invalid_merge_sha", metadata["validation_errors"])
        self.assertIn("invalid_correlation_id", metadata["validation_errors"])
        self.assertIn("invalid_generated_at", metadata["validation_errors"])


if __name__ == "__main__":
    unittest.main()
