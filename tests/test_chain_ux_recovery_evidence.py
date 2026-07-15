import unittest

from scripts.chain_ux_recovery_evidence import MAX_HISTORY, build_chain


class UxRecoveryEvidenceChainTests(unittest.TestCase):
    def test_adds_traceability_metadata(self):
        chain = build_chain(
            [],
            {
                "generated_at": "2026-07-15T12:00:00Z",
                "recovery_rate": 80,
                "average_recovery_seconds": 22,
                "ux_100_ready": True,
            },
            run_id="12345",
            head_sha="abcdef1234567890",
            source_workflow="recovery-trend",
        )
        self.assertEqual(chain[-1]["source_run_id"], "12345")
        self.assertEqual(chain[-1]["source_head_sha"], "abcdef1234567890")
        self.assertEqual(chain[-1]["source_workflow"], "recovery-trend")

    def test_is_idempotent_by_run_id(self):
        previous = [{
            "source_run_id": "12345",
            "source_head_sha": "oldsha123",
            "generated_at": "2026-07-15T11:00:00Z",
            "recovery_rate": 70.0,
            "average_recovery_seconds": 28.0,
            "ux_100_ready": True,
        }]
        chain = build_chain(
            previous,
            {
                "generated_at": "2026-07-15T12:00:00Z",
                "recovery_rate": 85,
                "average_recovery_seconds": 20,
                "ux_100_ready": True,
            },
            run_id="12345",
            head_sha="newsha123456",
            source_workflow="recovery-trend",
        )
        self.assertEqual(len(chain), 1)
        self.assertEqual(chain[0]["recovery_rate"], 85.0)
        self.assertEqual(chain[0]["source_head_sha"], "newsha123456")

    def test_limits_history(self):
        previous = [
            {
                "source_run_id": str(index),
                "generated_at": f"2026-07-15T{index % 24:02d}:00:00Z",
                "recovery_rate": 70,
                "average_recovery_seconds": 25,
                "ux_100_ready": True,
            }
            for index in range(MAX_HISTORY + 5)
        ]
        chain = build_chain(
            previous,
            {
                "recovery_rate": 90,
                "average_recovery_seconds": 18,
                "ux_100_ready": True,
            },
            run_id="latest",
            head_sha="abcdef123456",
            source_workflow="recovery-trend",
        )
        self.assertEqual(len(chain), MAX_HISTORY)
        self.assertEqual(chain[-1]["source_run_id"], "latest")

    def test_rejects_incomplete_evidence(self):
        with self.assertRaises(ValueError):
            build_chain(
                [],
                {"recovery_rate": 80},
                run_id="123",
                head_sha="abcdef123456",
                source_workflow="recovery-trend",
            )


if __name__ == "__main__":
    unittest.main()
