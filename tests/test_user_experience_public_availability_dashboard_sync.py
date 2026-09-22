import importlib.util, json, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def module(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

inject = module("inject_availability", "scripts/inject_user_experience_public_availability_card.py")
smoke = module("smoke_availability", "scripts/smoke_user_experience_public_availability_sync.py")

class PublicAvailabilityDashboardSyncTests(unittest.TestCase):
    def sample(self):
        return {"status":"PUBLIC_AVAILABILITY_STABLE","coverage":["DEV","STG","PROD"],"minimum_pass_rate":100,"sample_count":3,"stable_sequence":3,"common_fingerprint":"abc","drift_detected":False,"degradation_detected":False,"human_review_eligible":True,"mode":"report-only","production_blocker":False,"human_approval_required":True}

    def test_card_is_safe_and_idempotent(self):
        state={"cards":{"user_experience_public_availability":self.sample()}}
        card=inject.build(state)
        self.assertEqual(card["id"], inject.CARD_ID)
        self.assertFalse(card["production_blocker"])
        self.assertTrue(card["human_approval_required"])

    def test_fingerprint_detects_drift(self):
        a=self.sample(); b=dict(a); b["minimum_pass_rate"]=99
        self.assertNotEqual(smoke.fingerprint(a), smoke.fingerprint(b))

    def test_fallback_is_not_eligible(self):
        card=inject.build({})
        self.assertFalse(card["human_review_eligible"])
        self.assertEqual(card["status"], "PUBLIC_AVAILABILITY_REVIEW")

if __name__ == "__main__": unittest.main()
