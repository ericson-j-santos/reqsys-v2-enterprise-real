from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate_bacen_production_readiness.py"
spec = importlib.util.spec_from_file_location("validate_bacen_production_readiness", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

AS_OF = "2026-09-04T12:00:00Z"


def _policy(expected: int = 1) -> dict:
    return {
        "expected_obligations": expected,
        "obligation_readiness": {
            "production_acceptable_statuses": ["evidenciado", "nao_aplicavel"],
        },
    }


def _baseline(decision: str = "applicable", *, stale: bool = False) -> dict:
    applicability = {
        "family": "CMN-4893",
        "decision": decision,
        "decided_by": None,
        "decided_at": None,
        "rationale": None,
    }
    if decision == "not_applicable":
        applicability.update(
            {
                "decided_by": "responsavel-institucional",
                "decided_at": "2026-09-01T00:00:00Z",
                "rationale": "família formalmente fora do escopo da entidade",
            }
        )
    return {
        "applicability": applicability,
        "normative_baseline": {
            "referenced_documents": [
                {
                    "uid": "doc-test",
                    "checked_at": "2026-08-01" if stale else "2026-09-02",
                    "check_cycle_days": 7,
                    "hash_state": "captured",
                    "content_sha256": "a" * 64,
                }
            ]
        },
    }


def _obligation(*, assessment: dict | None = None) -> dict:
    return {
        "uid": "norm-test-0001",
        "code": "CMN4893-TEST-I",
        "assessment": assessment,
    }


def _valid_evidence(*, valid_until: str = "2026-12-31T00:00:00Z") -> dict:
    return {
        "uid": "evid-test-0001",
        "norm_uid": "norm-test-0001",
        "event_at": "2026-09-01T00:00:00Z",
        "collected_at": "2026-09-01T01:00:00Z",
        "valid_until": valid_until,
        "retention_until": "2031-09-01T00:00:00Z",
        "sha256": "b" * 64,
        "source": "teste",
    }


def _matrix(*, ready: bool = True) -> dict:
    controls = []
    for control_id in ("BACEN-01", "BACEN-08"):
        item = {
            "id": control_id,
            "status": "implemented" if ready else "partial",
            "decision_status": "approval_formally_canonicalized" if ready else "deferred_until_institutionalization",
        }
        if not ready:
            item["approval_status"] = "deferred_until_institutionalization"
        controls.append(item)
    return {"controls": controls}


def _reconciliation(*, ready: bool = True) -> dict:
    return {
        "controls": [
            {
                "control_id": control_id,
                "deferred_requirements": [] if ready else ["formal_requirement"],
                "production_gate": {
                    "required": True,
                    "block_when_deferred_requirements_missing": True,
                },
            }
            for control_id in ("BACEN-01", "BACEN-08")
        ]
    }


def _evaluate(
    *,
    decision: str = "applicable",
    assessment: dict | None = None,
    registry: dict | None = None,
    target: str = "PRODUCTION",
    stale_document: bool = False,
    formal_ready: bool = True,
) -> dict:
    return module.evaluate_readiness(
        baseline_v2=_baseline(decision, stale=stale_document),
        base_obligations={"obligations": [_obligation(assessment=assessment)]},
        extended_obligations={"obligations": []},
        evidence_registry=registry or {"applicability_decisions": [], "evidences": []},
        policy=_policy(),
        matrix=_matrix(ready=formal_ready),
        reconciliation=_reconciliation(ready=formal_ready),
        target_stage=target,
        as_of=AS_OF,
    )


def _codes(report: dict) -> set[str]:
    return {item["code"] for item in report["blockers"]}


def test_ready_applicable_obligation_with_valid_evidence_allows_production() -> None:
    report = _evaluate(
        assessment={"evaluated": True, "implementation": "complete"},
        registry={"applicability_decisions": [], "evidences": [_valid_evidence()]},
    )
    assert report["decision"] == "allowed"
    assert report["production_readiness"] == "ready"
    assert report["would_block_production"] is False
    assert report["status_counts"]["evidenciado"] == 1


def test_applicable_not_evaluated_obligation_blocks_production() -> None:
    report = _evaluate(assessment=None)
    assert report["decision"] == "blocked"
    assert "obligation_not_evaluated" in _codes(report)
    assert report["status_counts"]["nao_avaliado"] == 1


def test_complete_implementation_without_valid_evidence_blocks() -> None:
    report = _evaluate(assessment={"evaluated": True, "implementation": "complete"})
    assert "valid_evidence_missing" in _codes(report)
    assert report["status_counts"]["implementado"] == 1


def test_expired_evidence_is_not_accepted_for_production() -> None:
    report = _evaluate(
        assessment={"evaluated": True, "implementation": "complete"},
        registry={
            "applicability_decisions": [],
            "evidences": [_valid_evidence(valid_until="2026-09-03T23:59:59Z")],
        },
    )
    assert "valid_evidence_missing" in _codes(report)
    assert report["status_counts"]["implementado"] == 1


def test_formal_not_applicable_obligation_is_accepted() -> None:
    report = _evaluate(
        registry={
            "applicability_decisions": [
                {
                    "norm_uid": "norm-test-0001",
                    "decision": "not_applicable",
                    "decided_by": "responsavel",
                    "decided_at": "2026-09-01T00:00:00Z",
                    "rationale": "obrigação não se aplica ao escopo decidido",
                }
            ],
            "evidences": [],
        }
    )
    assert report["decision"] == "allowed"
    assert report["status_counts"]["nao_aplicavel"] == 1


def test_pending_family_blocks_without_inventing_which_obligations_are_applicable() -> None:
    report = _evaluate(decision="pending_decision")
    assert report["decision"] == "blocked"
    assert "family_applicability_pending" in _codes(report)
    assert report["status_counts"]["nao_derivado_por_aplicabilidade_pendente"] == 1
    assert "obligation_not_evaluated" not in _codes(report)


def test_formal_family_not_applicable_skips_obligation_assessment() -> None:
    report = _evaluate(decision="not_applicable")
    assert report["decision"] == "allowed"
    assert report["status_counts"]["nao_aplicavel"] == 1


def test_stale_live_document_blocks_production() -> None:
    report = _evaluate(
        assessment={"evaluated": True, "implementation": "complete"},
        registry={"applicability_decisions": [], "evidences": [_valid_evidence()]},
        stale_document=True,
    )
    assert "live_document_check_stale" in _codes(report)
    assert report["referenced_documents"]["stale_or_invalid"] == 1


def test_institutional_formal_gate_is_composed_into_gate_2() -> None:
    report = _evaluate(
        assessment={"evaluated": True, "implementation": "complete"},
        registry={"applicability_decisions": [], "evidences": [_valid_evidence()]},
        formal_ready=False,
    )
    assert report["institutional_formal_gate"]["decision"] == "blocked"
    assert sum(1 for item in report["blockers"] if item["code"] == "institutional_formal_gate_blocked") == 2


def test_non_production_stage_is_advisory_even_when_prod_would_block() -> None:
    report = _evaluate(decision="pending_decision", target="STAGING", formal_ready=False)
    assert report["decision"] == "allowed"
    assert report["enforced"] is False
    assert report["would_block_production"] is True
    assert report["main_branch_blocked_by_institutional_debt"] is False


def test_invalid_evidence_reference_fails_closed_for_production_readiness() -> None:
    evidence = _valid_evidence()
    evidence["norm_uid"] = "norm-desconhecido"
    report = _evaluate(
        assessment={"evaluated": True, "implementation": "complete"},
        registry={"applicability_decisions": [], "evidences": [evidence]},
    )
    assert "unknown_evidence_norm_uid" in _codes(report)
    assert "valid_evidence_missing" in _codes(report)


def test_repository_state_is_advisory_on_main_but_would_block_production() -> None:
    root = Path(__file__).resolve().parents[1]
    report = module.evaluate_readiness(
        baseline_v2=module.load_yaml(root / "governance/bacen/normative/NORMATIVE-BASELINE-V2.yaml"),
        base_obligations=module.load_yaml(root / "governance/bacen/normative/NORMATIVE-BASELINE.yaml"),
        extended_obligations=module.load_yaml(root / "governance/bacen/normative/NORMATIVE-OBLIGATIONS-EXTENDED.yaml"),
        evidence_registry=module.load_yaml(root / "governance/bacen/normative/EVIDENCE-REGISTRY.yaml"),
        policy=module.load_yaml(root / "governance/bacen/normative/PRODUCTION-READINESS-POLICY.yaml"),
        matrix=module.load_yaml(root / "governance/bacen/BACEN-CONTROL-MATRIX.yaml"),
        reconciliation=module.load_yaml(root / "governance/bacen/BACEN-GOVERNANCE-RECONCILIATION.yaml"),
        target_stage="DEVELOPMENT",
        as_of=AS_OF,
    )
    assert report["decision"] == "allowed"
    assert report["production_readiness"] == "blocked"
    assert report["would_block_production"] is True
    assert report["obligations_total"] == 57
    assert report["status_counts"]["nao_derivado_por_aplicabilidade_pendente"] == 57
    assert "family_applicability_pending" in _codes(report)
