import unittest

from scripts.merge_ux_runtime_environment_history import MAX_HISTORY, merge_history


class MergeRuntimeEnvironmentHistoryTests(unittest.TestCase):
    def test_deduplicates_and_rejects_unverified_evidence(self):
        verified = {
            "evidence_source": "runtime",
            "verification_status": "verified",
            "environment": "dev",
            "correlation_id": "runtime-dev-0001",
            "merge_sha": "a" * 40,
            "timestamp": "2026-07-15T10:00:00Z",
        }
        result = merge_history([verified], [verified, {**verified, "evidence_source": "unverified"}])
        self.assertEqual(result, [verified])

    def test_keeps_last_n_ordered_samples(self):
        samples = []
        for index in range(MAX_HISTORY + 5):
            samples.append({
                "evidence_source": "runtime",
                "verification_status": "verified",
                "environment": "stg",
                "correlation_id": f"runtime-stg-{index:04d}",
                "merge_sha": f"{index:040x}"[-40:],
                "timestamp": f"2026-07-{(index % 28) + 1:02d}T10:00:00Z",
            })
        result = merge_history([], samples)
        self.assertEqual(len(result), MAX_HISTORY)

    def test_ignores_unknown_environment(self):
        result = merge_history([], [{
            "evidence_source": "runtime",
            "verification_status": "verified",
            "environment": "qa",
            "correlation_id": "runtime-qa-0001",
            "merge_sha": "b" * 40,
        }])
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
