from scripts.teams_notification_event_policy import (
    delivery_result_decision,
    remediation_decision,
    suppression_class,
    triage_decision,
    workflow_run_delivery_decision,
)

VALID_TRIAGE = {
    "schema_version": "1.0.0",
    "run_id": 38317762263,
    "pr": {"number": 2556, "head_sha": "a" * 40, "run_head_sha": "a" * 40, "sha_current": True},
    "triage": {"root_cause": "transient CI failure", "category": "ci"},
    "analyzed_sha": "a" * 40,
    "result": "triaged",
}


def test_triage_requires_success_and_material_evidence() -> None:
    assert triage_decision("success", VALID_TRIAGE) == (True, "material_triage")
    for conclusion in ("skipped", "cancelled", "failure"):
        allowed, reason = triage_decision(conclusion, VALID_TRIAGE)
        assert not allowed and reason == f"source_conclusion_{conclusion}"
    assert triage_decision("success", None) == (False, "triage_evidence_missing")
    assert triage_decision("success", {}) == (False, "triage_evidence_missing")
    invalid = dict(VALID_TRIAGE, analyzed_sha="n/a")
    assert triage_decision("success", invalid) == (False, "triage_evidence_invalid_identity")
    mismatch = dict(VALID_TRIAGE, analyzed_sha="b" * 40)
    assert triage_decision("success", mismatch) == (False, "triage_evidence_sha_mismatch")
    assert triage_decision("success", dict(VALID_TRIAGE, schema_version="2.0")) == (
        False,
        "triage_evidence_schema_unknown",
    )
    assert triage_decision("success", dict(VALID_TRIAGE, run_id=None)) == (
        False,
        "triage_evidence_run_invalid",
    )


def test_remediation_preserves_no_action_filter() -> None:
    assert remediation_decision({"reruns_executed": 0}) == (False, "no_material_remediation")
    assert remediation_decision({"reruns_executed": 2}) == (False, "invalid_remediation_pr")
    material = {"reruns_executed": 2, "target_pr_number": 2556, "target_head_sha": "b" * 40}
    assert remediation_decision(material) == (True, "material_remediation")
    assert remediation_decision(dict(material, target_head_sha="n/a")) == (False, "invalid_remediation_sha")


def test_only_allowlisted_reasons_are_material_noop() -> None:
    for reason in (
        "source_conclusion_skipped",
        "source_conclusion_cancelled",
        "no_material_remediation",
        "workflow_run_not_supported",
    ):
        assert suppression_class(reason) == "material_noop"
    for reason in (
        "triage_evidence_missing",
        "triage_evidence_schema_unknown",
        "triage_evidence_sha_mismatch",
        "invalid_remediation_sha",
    ):
        assert suppression_class(reason) == "evidence_failure"


def test_delivery_result_contract_is_strict_per_route() -> None:
    gateway = {"entregue": True, "status_code": 202}
    assert delivery_result_decision("gateway", gateway) == (True, "gateway_delivery_confirmed")
    for value in (None, False, "true", 1):
        assert not delivery_result_decision("gateway", dict(gateway, entregue=value))[0]

    webhook = {"success": True, "route": "webhook", "status_code": 200}
    assert delivery_result_decision("webhook_fallback", webhook) == (
        True,
        "webhook_delivery_confirmed",
    )
    for mutation in (
        {"success": None},
        {"success": False},
        {"success": "true"},
        {"route": "graph_app_channel"},
        {"route": None},
        {"status_code": "200"},
        {"status_code": 500},
        {"dry_run": "false"},
        {"suppressed": True},
    ):
        assert not delivery_result_decision("webhook_fallback", dict(webhook, **mutation))[0]


def test_recovery_requires_identity_bound_confirmation_step() -> None:
    run_id = 38317762263
    head_sha = "c" * 40
    payload = {
        "total_count": 1,
        "jobs": [{
            "name": "Enviar commit ao Teams",
            "run_id": run_id,
            "head_sha": head_sha,
            "steps": [{"name": "Confirmar entrega real", "conclusion": "success"}],
        }],
    }
    assert workflow_run_delivery_decision(run_id, head_sha, payload) == ("delivered", "real_delivery_confirmed")
    assert workflow_run_delivery_decision(run_id + 1, head_sha, payload)[0] == "observation_unavailable"
    assert workflow_run_delivery_decision(run_id, "d" * 40, payload)[0] == "observation_unavailable"
    assert workflow_run_delivery_decision(run_id, head_sha, {"schema": "unknown"}) == (
        "observation_unavailable",
        "jobs_schema_invalid",
    )


def test_normal_suppression_is_not_delivery_or_failure() -> None:
    payload = {
        "total_count": 1,
        "jobs": [{
            "name": "Enviar commit ao Teams",
            "run_id": 7,
            "head_sha": "e" * 40,
            "steps": [{"name": "Confirmar supressão sem mudança material", "conclusion": "success"}],
        }],
    }
    assert workflow_run_delivery_decision(7, "e" * 40, payload) == (
        "suppressed",
        "material_notification_suppressed",
    )


def test_observation_unavailable_is_distinct_from_delivery_failure() -> None:
    assert workflow_run_delivery_decision(7, "e" * 40, None) == (
        "observation_unavailable",
        "jobs_request_unavailable",
    )
    incomplete = {"total_count": 2, "jobs": [{"name": "Enviar commit ao Teams"}]}
    assert workflow_run_delivery_decision(7, "e" * 40, incomplete) == (
        "observation_unavailable",
        "jobs_page_incomplete",
    )
