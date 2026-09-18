import unittest

from scripts.validate_bacen_regulatory_no_regression import (
    compare_snapshots,
    derive_snapshot,
)

AS_OF = "2026-09-03T03:30:00Z"


def obligation(uid="norm-test-1", assessment=None, applicability_decision=None):
    item = {"uid": uid, "code": uid.upper(), "assessment": assessment}
    if applicability_decision is not None:
        item["applicability_decision"] = applicability_decision
    return item


def evidence(uid="ev-1", norm_uid="norm-test-1", valid_until="2026-09-04T00:00:00Z"):
    return {
        "uid": uid,
        "norm_uid": norm_uid,
        "event_at": "2026-09-01T00:00:00Z",
        "collected_at": "2026-09-01T01:00:00Z",
        "valid_until": valid_until,
        "retention_until": "2031-09-01T00:00:00Z",
        "sha256": "a" * 64,
        "source": "test",
    }


class NoRegressionGateTests(unittest.TestCase):
    def status(self, item, evidences=(), applicability=None):
        snapshot = derive_snapshot(
            obligations=[item],
            applicability=applicability,
            evidences=list(evidences),
            as_of=AS_OF,
        )
        return snapshot[item["uid"]]

    def test_current_unassessed_state_is_stable(self):
        base = {"norm-a": "nao_avaliado"}
        head = {"norm-a": "nao_avaliado"}
        result = compare_snapshots(base, head)
        self.assertEqual(result["regressions"], [])
        self.assertEqual(result["unchanged"], 1)

    def test_preexisting_gap_does_not_block(self):
        result = compare_snapshots({"norm-a": "lacuna"}, {"norm-a": "lacuna"})
        self.assertEqual(result["regressions"], [])

    def test_evidenced_to_implemented_is_regression(self):
        result = compare_snapshots({"norm-a": "evidenciado"}, {"norm-a": "implementado"})
        self.assertEqual(len(result["regressions"]), 1)
        self.assertEqual(result["regressions"][0]["reason"], "derived_status_regression")

    def test_partial_to_implemented_is_improvement(self):
        result = compare_snapshots({"norm-a": "parcial"}, {"norm-a": "implementado"})
        self.assertEqual(result["regressions"], [])
        self.assertEqual(len(result["improvements"]), 1)

    def test_removed_obligation_blocks(self):
        result = compare_snapshots({"norm-a": "nao_avaliado"}, {})
        self.assertEqual(len(result["regressions"]), 1)
        self.assertEqual(result["regressions"][0]["reason"], "obligation_removed")

    def test_scope_reduction_to_not_applicable_blocks(self):
        result = compare_snapshots({"norm-a": "implementado"}, {"norm-a": "nao_aplicavel"})
        self.assertEqual(len(result["regressions"]), 1)
        self.assertEqual(result["regressions"][0]["reason"], "applicability_scope_reduction")

    def test_scope_expansion_from_not_applicable_does_not_block(self):
        result = compare_snapshots({"norm-a": "nao_aplicavel"}, {"norm-a": "nao_avaliado"})
        self.assertEqual(result["regressions"], [])
        self.assertEqual(result["improvements"][0]["reason"], "applicability_scope_expansion")

    def test_new_obligation_does_not_block(self):
        result = compare_snapshots({}, {"norm-a": "nao_avaliado"})
        self.assertEqual(result["regressions"], [])
        self.assertEqual(result["added"], ["norm-a"])

    def test_derived_status_uses_same_frozen_as_of(self):
        assessment = {"evaluated": True, "implementation": "complete"}
        item = obligation(assessment=assessment)
        ev = evidence(valid_until=AS_OF)
        base = derive_snapshot(obligations=[item], applicability=None, evidences=[ev], as_of=AS_OF)
        head = derive_snapshot(obligations=[item], applicability=None, evidences=[ev], as_of=AS_OF)
        self.assertEqual(base["norm-test-1"], "evidenciado")
        self.assertEqual(head["norm-test-1"], "evidenciado")
        self.assertEqual(compare_snapshots(base, head)["regressions"], [])

    def test_expired_evidence_degrades_both_sides_equally_at_same_t(self):
        assessment = {"evaluated": True, "implementation": "complete"}
        item = obligation(assessment=assessment)
        ev = evidence(valid_until="2026-09-02T00:00:00Z")
        base = derive_snapshot(obligations=[item], applicability=None, evidences=[ev], as_of=AS_OF)
        head = derive_snapshot(obligations=[item], applicability=None, evidences=[ev], as_of=AS_OF)
        self.assertEqual(base["norm-test-1"], "implementado")
        self.assertEqual(head["norm-test-1"], "implementado")
        self.assertEqual(compare_snapshots(base, head)["regressions"], [])

    def test_not_applicable_decision_is_normalized(self):
        decision = {
            "decision": "not_applicable",
            "decided_by": "responsavel",
            "decided_at": "2026-09-01T00:00:00Z",
            "rationale": "fora do escopo",
        }
        self.assertEqual(self.status(obligation(applicability_decision=decision)), "nao_aplicavel")


if __name__ == "__main__":
    unittest.main()
