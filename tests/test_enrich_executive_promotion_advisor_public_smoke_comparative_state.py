from __future__ import annotations

import unittest

from scripts.enrich_executive_promotion_advisor_public_smoke_comparative_state import (
    enrich_executive_brief,
    enrich_runtime_index,
    summarize,
)


def history(dev_rate: float = 100.0, stg_rate: float = 100.0, prod_rate: float = 100.0) -> dict:
    return {
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
        "generated_at": "2026-07-11T16:00:00+00:00",
        "environments": {
            "dev": {"summary": {"sample_count": 10, "pass_rate_percent": dev_rate, "stable_streak": 10, "latest_status": "passed", "latest_decision": "PUBLIC_SMOKE_PASSED", "eligible_for_human_review": False}},
            "stg": {"summary": {"sample_count": 10, "pass_rate_percent": stg_rate, "stable_streak": 10, "latest_status": "passed", "latest_decision": "PUBLIC_SMOKE_PASSED", "eligible_for_human_review": False}},
            "prod": {"summary": {"sample_count": 10, "pass_rate_percent": prod_rate, "stable_streak": 10, "latest_status": "passed", "latest_decision": "PUBLIC_SMOKE_PASSED", "eligible_for_human_review": False}},
        },
    }


class AdvisorPublicSmokeComparativeStateTests(unittest.TestCase):
    def test_comparacao_completa_elegivel_apenas_para_revisao_humana(self) -> None:
        card = summarize(history())
        self.assertTrue(card["full_environment_coverage"])
        self.assertTrue(card["eligible_for_gate_review"])
        self.assertEqual("eligible-for-human-review", card["trend"])
        self.assertFalse(card["production_blocker"])
        self.assertTrue(card["human_approval_required"])

    def test_cobertura_incompleta_nao_promove(self) -> None:
        payload = history()
        del payload["environments"]["prod"]
        card = summarize(payload)
        self.assertFalse(card["full_environment_coverage"])
        self.assertFalse(card["eligible_for_gate_review"])
        self.assertEqual("insufficient-environment-coverage", card["trend"])

    def test_ambiente_com_taxa_baixa_resulta_atencao(self) -> None:
        card = summarize(history(prod_rate=70.0))
        self.assertEqual("attention", card["trend"])
        self.assertFalse(card["eligible_for_gate_review"])
        self.assertEqual(70.0, card["minimum_pass_rate_percent"])

    def test_estado_de_producao_e_preservado(self) -> None:
        runtime = {"summary": {"production_ready": True}, "cards": {}, "links": {}, "guardrails": []}
        brief = {"production_ready": True, "indicadores": {}, "semaforo_executivo": {}, "evidencias": {}}
        card = summarize(history())
        enriched_runtime = enrich_runtime_index(runtime, card)
        enriched_brief = enrich_executive_brief(brief, card)
        self.assertTrue(enriched_runtime["summary"]["production_ready"])
        self.assertTrue(enriched_brief["production_ready"])
        self.assertFalse(enriched_runtime["cards"]["executive_promotion_advisor_public_smoke_comparison"]["production_blocker"])

    def test_enriquecimento_e_idempotente(self) -> None:
        card = summarize(history())
        first = enrich_runtime_index({"cards": {}, "summary": {}, "links": {}, "guardrails": []}, card)
        second = enrich_runtime_index(first, card)
        self.assertEqual(first, second)
        self.assertEqual(1, second["guardrails"].count("executive_promotion_advisor_public_smoke_comparison_report_only"))


if __name__ == "__main__":
    unittest.main()
