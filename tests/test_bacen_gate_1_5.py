from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.bacen_gate_1_5 import compare_snapshots


AS_OF_BEFORE_EXPIRY = "2026-09-02T23:59:00Z"
AS_OF_AFTER_EXPIRY = "2026-09-03T00:01:00Z"


def evidence(valid_until: str = "2026-09-03T00:00:00Z") -> dict:
    return {
        "uid": "evid-001",
        "norm_uid": "norm-001",
        "event_at": "2026-01-01T00:00:00Z",
        "collected_at": "2026-01-02T00:00:00Z",
        "valid_until": valid_until,
        "retention_until": "2031-01-01T00:00:00Z",
        "sha256": "a" * 64,
        "source": "institutional://evidence/001",
    }


def obligation(
    *,
    uid: str = "norm-001",
    code: str = "TEST-001",
    implementation: str | None = "complete",
    evidences: list[dict] | None = None,
    applicability_decision: dict | None = None,
) -> dict:
    item = {
        "uid": uid,
        "code": code,
        "title": "Obrigação de teste",
        "mapping": {"state": "pending", "corporate_refs": [], "implementation_refs": []},
        "assessment": None
        if implementation is None
        else {"evaluated": True, "implementation": implementation},
    }
    if evidences is not None:
        item["evidences"] = evidences
    if applicability_decision is not None:
        item["applicability_decision"] = applicability_decision
    return item


def write_snapshot(root: Path, obligations: list[dict]) -> None:
    directory = root / "governance/bacen/normative"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "NORMATIVE-BASELINE.yaml").write_text(
        yaml.safe_dump({"schema_version": "1.0.0", "obligations": obligations}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    (directory / "NORMATIVE-OBLIGATIONS-EXTENDED.yaml").write_text(
        yaml.safe_dump({"schema_version": "1.0.0", "obligations": []}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


class Gate15Tests(unittest.TestCase):
    def compare(self, base_items: list[dict], head_items: list[dict], *, as_of: str) -> dict:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base = root / "base"
            head = root / "head"
            write_snapshot(base, base_items)
            write_snapshot(head, head_items)
            return compare_snapshots(base_root=base, head_root=head, as_of=as_of)

    def test_mesmo_as_of_impede_falso_positivo_na_virada_de_validade(self):
        item = obligation(evidences=[evidence()])

        before = self.compare([item], [item], as_of=AS_OF_BEFORE_EXPIRY)
        after = self.compare([item], [item], as_of=AS_OF_AFTER_EXPIRY)

        self.assertEqual(before["decision"], "pass")
        self.assertEqual(before["transitions"][0]["base_status"], "evidenciado")
        self.assertEqual(before["transitions"][0]["head_status"], "evidenciado")
        self.assertEqual(after["decision"], "pass")
        self.assertEqual(after["transitions"][0]["base_status"], "implementado")
        self.assertEqual(after["transitions"][0]["head_status"], "implementado")
        self.assertTrue(before["same_as_of_for_base_and_head"])
        self.assertTrue(after["same_as_of_for_base_and_head"])

    def test_remocao_real_de_evidencia_bloqueia(self):
        base = obligation(evidences=[evidence()])
        head = obligation(evidences=[])
        result = self.compare([base], [head], as_of=AS_OF_BEFORE_EXPIRY)

        self.assertEqual(result["decision"], "blocked")
        self.assertEqual(result["regressions"][0]["base_status"], "evidenciado")
        self.assertEqual(result["regressions"][0]["head_status"], "implementado")
        self.assertEqual(result["regressions"][0]["reason"], "regressao_de_status_derivado")

    def test_progressao_de_parcial_para_implementado_e_permitida(self):
        base = obligation(implementation="partial")
        head = obligation(implementation="complete")
        result = self.compare([base], [head], as_of=AS_OF_BEFORE_EXPIRY)

        self.assertEqual(result["decision"], "pass")
        self.assertEqual(result["regression_count"], 0)

    def test_remocao_de_obrigacao_bloqueia(self):
        result = self.compare([obligation()], [], as_of=AS_OF_BEFORE_EXPIRY)
        self.assertEqual(result["decision"], "blocked")
        self.assertEqual(result["regressions"][0]["reason"], "obrigacao_removida")

    def test_alteracao_do_code_para_mesmo_uid_bloqueia(self):
        result = self.compare(
            [obligation(code="TEST-001")],
            [obligation(code="TEST-RENOMEADO")],
            as_of=AS_OF_BEFORE_EXPIRY,
        )
        self.assertEqual(result["decision"], "blocked")
        self.assertEqual(result["regressions"][0]["reason"], "identidade_legivel_alterada")

    def test_transicao_para_nao_aplicavel_exige_revisao_explicita(self):
        decision = {
            "decision": "nao_aplicavel",
            "decided_by": "responsavel-institucional",
            "decided_at": "2026-08-01T00:00:00Z",
            "rationale": "fora do escopo formal",
        }
        result = self.compare(
            [obligation(implementation="partial")],
            [obligation(implementation="partial", applicability_decision=decision)],
            as_of=AS_OF_BEFORE_EXPIRY,
        )
        self.assertEqual(result["decision"], "blocked")
        self.assertEqual(
            result["regressions"][0]["reason"],
            "transicao_nao_aplicavel_exige_revisao_explicita",
        )

    def test_nova_obrigacao_nao_e_regressao(self):
        result = self.compare(
            [obligation()],
            [obligation(), obligation(uid="norm-002", code="TEST-002", implementation=None)],
            as_of=AS_OF_BEFORE_EXPIRY,
        )
        self.assertEqual(result["decision"], "pass")
        self.assertEqual(result["new_obligations"], ["norm-002"])


if __name__ == "__main__":
    unittest.main()
