import unittest

from scripts.enrich_executive_final_sync_history_state import CARD_KEY, build_state, enrich


def history(environment: str, *, count: int = 3, passed: bool = True, synchronized: bool = True, fingerprint: str = "fp-1") -> dict:
    status = "PUBLIC_FINAL_SYNC_OK" if passed else "PUBLIC_FINAL_SYNC_REVIEW"
    return {
        "samples": [
            {
                "environment": environment,
                "status": status,
                "synchronized": synchronized,
                "fingerprint": fingerprint,
            }
            for _ in range(count)
        ],
        "summary": {
            "sample_count": count,
            "pass_rate_percent": 100.0 if passed else 0.0,
            "stable_sequence": count if passed else 0,
        },
    }


class ExecutiveFinalSyncHistoryStateTest(unittest.TestCase):
    def test_complete_evidence_is_human_review_only(self):
        state = build_state({env: history(env) for env in ("dev", "stg", "prod")})
        self.assertEqual("eligible-for-human-review", state["status"])
        self.assertTrue(state["no_drift"])
        self.assertTrue(state["eligible_for_human_review"])
        self.assertFalse(state["production_blocker"])
        self.assertEqual("report-only", state["mode"])

    def test_missing_environment_is_not_eligible(self):
        state = build_state({"dev": history("dev"), "stg": history("stg")})
        self.assertEqual("insufficient-environment-coverage", state["status"])
        self.assertEqual(["prod"], state["missing_environments"])
        self.assertFalse(state["eligible_for_human_review"])

    def test_fingerprint_drift_is_detected(self):
        histories = {env: history(env) for env in ("dev", "stg", "prod")}
        histories["prod"] = history("prod", fingerprint="fp-2")
        state = build_state(histories)
        self.assertEqual("drift-detected", state["status"])
        self.assertFalse(state["no_drift"])
        self.assertFalse(state["production_blocker"])

    def test_insufficient_samples_keep_collecting(self):
        state = build_state({env: history(env, count=2) for env in ("dev", "stg", "prod")})
        self.assertEqual("collecting-evidence", state["status"])
        self.assertFalse(state["eligible_for_human_review"])

    def test_review_status_is_attention(self):
        histories = {env: history(env) for env in ("dev", "stg", "prod")}
        histories["stg"] = history("stg", passed=False)
        state = build_state(histories)
        self.assertEqual("attention", state["status"])

    def test_enrich_is_idempotent_and_preserves_production_state(self):
        runtime = {"production_ready": True, "cards": {"existing": {"status": "ok"}}}
        brief = {"production_ready": True}
        histories = {env: history(env) for env in ("dev", "stg", "prod")}
        first_runtime, first_brief = enrich(runtime, brief, histories)
        second_runtime, second_brief = enrich(first_runtime, first_brief, histories)
        self.assertEqual(first_runtime, second_runtime)
        self.assertEqual(first_brief, second_brief)
        self.assertTrue(second_runtime["production_ready"])
        self.assertTrue(second_brief["production_ready"])
        self.assertIn(CARD_KEY, second_runtime["cards"])


if __name__ == "__main__":
    unittest.main()
