from __future__ import annotations

import unittest

from scripts.bacen_derived_status import (
    EvidencePolicy,
    derive_status,
    derive_temporal_fields,
    evidence_is_valid,
    evidence_must_be_retained,
)


OBLIGATION = {"uid": "norm-test-001", "code": "TEST-001"}
AS_OF = "2026-09-02T22:00:00Z"


def evidence(**overrides):
    payload = {
        "uid": "evid-001",
        "norm_uid": "norm-test-001",
        "event_at": "2026-01-01T00:00:00Z",
        "collected_at": "2026-01-02T00:00:00Z",
        "valid_until": "2026-12-31T00:00:00Z",
        "retention_until": "2031-01-01T00:00:00Z",
        "sha256": "a" * 64,
        "source": "institutional://evidence/001",
    }
    payload.update(overrides)
    return payload


class DerivedStatusTests(unittest.TestCase):
    def test_sem_avaliacao_deriva_nao_avaliado(self):
        self.assertEqual(derive_status(obligation=OBLIGATION, as_of=AS_OF), "nao_avaliado")

    def test_nao_avaliado_nao_vira_parcial_automaticamente(self):
        self.assertEqual(
            derive_status(obligation=OBLIGATION, as_of=AS_OF, assessment={"evaluated": False}),
            "nao_avaliado",
        )

    def test_nao_aplicavel_exige_decisao_completa(self):
        with self.assertRaises(ValueError):
            derive_status(
                obligation=OBLIGATION,
                as_of=AS_OF,
                applicability_decision={"decision": "nao_aplicavel", "rationale": "fora do escopo"},
            )

    def test_nao_aplicavel_com_decisao_valida(self):
        self.assertEqual(
            derive_status(
                obligation=OBLIGATION,
                as_of=AS_OF,
                applicability_decision={
                    "decision": "nao_aplicavel",
                    "decided_by": "responsavel-institucional",
                    "decided_at": "2026-08-01T00:00:00Z",
                    "rationale": "escopo formalmente excluido",
                },
            ),
            "nao_aplicavel",
        )

    def test_lacuna_quando_avaliado_sem_implementacao(self):
        self.assertEqual(
            derive_status(obligation=OBLIGATION, as_of=AS_OF, assessment={"evaluated": True, "implementation": "none"}),
            "lacuna",
        )

    def test_parcial_quando_implementacao_incompleta(self):
        self.assertEqual(
            derive_status(obligation=OBLIGATION, as_of=AS_OF, assessment={"evaluated": True, "implementation": "partial"}),
            "parcial",
        )

    def test_implementado_sem_evidencia_valida(self):
        self.assertEqual(
            derive_status(obligation=OBLIGATION, as_of=AS_OF, assessment={"evaluated": True, "implementation": "complete"}),
            "implementado",
        )

    def test_evidenciado_com_evidencia_valida(self):
        self.assertEqual(
            derive_status(
                obligation=OBLIGATION,
                as_of=AS_OF,
                assessment={"evaluated": True, "implementation": "complete"},
                evidences=[evidence()],
            ),
            "evidenciado",
        )

    def test_evidencia_vencida_nao_evidencia_mas_permanece_retida(self):
        expired = evidence(valid_until="2026-06-30T00:00:00Z")
        self.assertFalse(evidence_is_valid(expired, AS_OF))
        self.assertTrue(evidence_must_be_retained(expired, AS_OF))
        self.assertEqual(
            derive_status(
                obligation=OBLIGATION,
                as_of=AS_OF,
                assessment={"evaluated": True, "implementation": "complete"},
                evidences=[expired],
            ),
            "implementado",
        )

    def test_limite_de_validade_e_inclusivo(self):
        at_boundary = evidence(valid_until=AS_OF)
        self.assertTrue(evidence_is_valid(at_boundary, AS_OF))

    def test_tempos_derivam_de_event_at_nao_collected_at(self):
        result = derive_temporal_fields("2026-01-01T00:00:00Z", EvidencePolicy(validity_days=365, retention_days=1825))
        self.assertEqual(result["valid_until"], "2027-01-01T00:00:00Z")
        self.assertEqual(result["retention_until"], "2030-12-31T00:00:00Z")

    def test_status_manual_na_obrigacao_e_rejeitado(self):
        with self.assertRaises(ValueError):
            derive_status(obligation={**OBLIGATION, "status": "evidenciado"}, as_of=AS_OF)

    def test_status_manual_no_assessment_e_rejeitado(self):
        with self.assertRaises(ValueError):
            derive_status(
                obligation=OBLIGATION,
                as_of=AS_OF,
                assessment={"evaluated": True, "implementation": "complete", "status": "evidenciado"},
            )

    def test_as_of_precisa_ser_utc(self):
        with self.assertRaises(ValueError):
            derive_status(obligation=OBLIGATION, as_of="2026-09-02T22:00:00-03:00")


if __name__ == "__main__":
    unittest.main()
