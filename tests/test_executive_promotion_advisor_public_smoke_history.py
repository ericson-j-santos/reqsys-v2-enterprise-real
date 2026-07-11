from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.build_executive_promotion_advisor_public_smoke_history import build
from scripts.smoke_executive_promotion_advisor_homologation_trend_public import build_evidence


class AdvisorPublicSmokeTests(unittest.TestCase):
    def test_smoke_publico_valido_permanece_report_only(self) -> None:
        html = '<section id="executive-promotion-advisor-homologation-trend-card"></section>\nrenderExecutivePromotionAdvisorHomologationTrend(payload);'
        runtime = json.dumps({
            "cards": {
                "executive_promotion_advisor_homologation_trend": {
                    "mode": "report-only",
                    "production_blocker": False,
                    "human_approval_required": True,
                    "eligible_for_gate_review": False,
                    "trend": "stable",
                    "sample_count": 10,
                    "stable_streak": 8,
                    "full_homologation_rate_percent": 100,
                }
            }
        })
        with patch(
            "scripts.smoke_executive_promotion_advisor_homologation_trend_public.fetch_text",
            side_effect=[(200, html), (200, runtime)],
        ):
            evidence = build_evidence("dev", "https://example.test")

        self.assertEqual("passed", evidence["status"])
        self.assertFalse(evidence["production_blocker"])
        self.assertTrue(evidence["human_approval_required"])

    def test_smoke_inseguro_resulta_review_sem_bloqueio(self) -> None:
        html = '<section id="executive-promotion-advisor-homologation-trend-card"></section>\nrenderExecutivePromotionAdvisorHomologationTrend(payload);'
        runtime = json.dumps({
            "cards": {
                "executive_promotion_advisor_homologation_trend": {
                    "mode": "blocking",
                    "production_blocker": True,
                    "human_approval_required": False,
                    "eligible_for_gate_review": True,
                }
            }
        })
        with patch(
            "scripts.smoke_executive_promotion_advisor_homologation_trend_public.fetch_text",
            side_effect=[(200, html), (200, runtime)],
        ):
            evidence = build_evidence("prod", "https://example.test")

        self.assertEqual("review", evidence["status"])
        self.assertFalse(evidence["production_blocker"])
        self.assertTrue(evidence["human_approval_required"])

    def test_historico_separa_ambientes_e_e_idempotente(self) -> None:
        evidence = {
            "generated_at": "2026-07-11T10:00:00+00:00",
            "environment": "dev",
            "status": "passed",
            "decision": "PUBLIC_SMOKE_PASSED",
            "public_url": "https://dev.example/",
            "advisor_trend": {"trend": "stable", "sample_count": 10, "eligible_for_gate_review": False},
            "errors": [],
            "production_blocker": False,
        }
        first = build({}, evidence)
        second = build(first, evidence)
        self.assertEqual(1, second["environments"]["dev"]["summary"]["sample_count"])
        self.assertEqual(100.0, second["environments"]["dev"]["summary"]["pass_rate_percent"])
        self.assertFalse(second["production_blocker"])

        stg = dict(evidence)
        stg["environment"] = "stg"
        stg["public_url"] = "https://stg.example/"
        combined = build(second, stg)
        self.assertEqual({"dev", "stg"}, set(combined["environments"]))
        self.assertEqual(2, combined["summary"]["sample_count"])


if __name__ == "__main__":
    unittest.main()
