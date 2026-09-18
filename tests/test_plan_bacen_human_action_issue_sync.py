from scripts.plan_bacen_human_action_issue_sync import (
    build_plan,
    body_for,
    deferred_body_for,
    deferred_title_for,
    title_for,
)


def item(control_id="BACEN-08", status="partial"):
    return {
        "control_id": control_id,
        "title": "Responsável executivo e relatório anual",
        "status": status,
        "priority": "P0",
        "responsible_role": "GOVERNANCE",
        "required_action": "formal_designation_and_signed_report",
        "evidence_reference": "artifacts/bacen/bacen-08.json",
        "lifecycle_stage": "PRODUCTION",
        "institutional_gate_stage": "PRODUCTION",
    }


def deferred_item(control_id="BACEN-02"):
    return {
        "control_id": control_id,
        "title": "Autenticação forte e acesso privilegiado",
        "status": "partial",
        "priority": "P0",
        "responsible_role": "SECURITY",
        "required_action": "continue_technical_access_control_evidence_until_production_gate",
        "evidence_reference": "artifacts/bacen/bacen-02.json",
        "lifecycle_stage": "DEVELOPMENT",
        "institutional_gate_stage": "PRODUCTION",
        "backlog_status": "deferred_until_institutionalization",
        "human_action_required_now": False,
    }


def issue(number, source, state="open"):
    return {
        "number": number,
        "title": title_for(source),
        "body": body_for(source),
        "state": state,
        "labels": [
            {"name": "bacen"},
            {"name": "formal-action"},
            {"name": "priority-p0"},
            {"name": f"owner-{str(source['responsible_role']).lower().replace('_', '-')}"},
        ],
    }


def test_creates_issue_for_new_pending_control():
    plan = build_plan({"items": [item()]}, [])
    assert plan["summary"] == {
        "create": 1,
        "update": 0,
        "defer": 0,
        "close": 0,
        "total_operations": 1,
    }
    assert plan["operations"][0]["action"] == "create"
    assert plan["approvals_fabricated"] is False


def test_reopens_closed_issue_when_control_is_still_pending():
    source = item()
    plan = build_plan({"items": [source]}, [issue(12, source, state="closed")])
    assert plan["operations"][0]["action"] == "update"
    assert plan["operations"][0]["state"] == "open"


def test_closes_issue_when_control_is_no_longer_pending():
    source = item()
    plan = build_plan({"items": []}, [issue(15, source)])
    assert plan["operations"][0]["action"] == "close"
    assert plan["operations"][0]["control_id"] == "BACEN-08"


def test_unchanged_canonical_issue_is_idempotent():
    source = item()
    plan = build_plan({"items": [source]}, [issue(21, source)])
    assert plan["operations"] == []
    assert plan["summary"]["total_operations"] == 0


def test_defers_existing_open_issue_without_claiming_implementation():
    source = deferred_item()
    current = issue(31, source, state="open")
    plan = build_plan({"items": [], "deferred_items": [source]}, [current])

    assert plan["pending_controls"] == 0
    assert plan["deferred_controls"] == 1
    assert plan["summary"]["defer"] == 1
    operation = plan["operations"][0]
    assert operation["action"] == "defer"
    assert operation["title"] == deferred_title_for(source)
    assert operation["body"] == deferred_body_for(source)
    assert "não foi promovido para `implemented`" in operation["comment"]


def test_already_deferred_closed_issue_is_idempotent():
    source = deferred_item()
    current = {
        "number": 32,
        "title": deferred_title_for(source),
        "body": deferred_body_for(source),
        "state": "closed",
        "labels": [
            {"name": "bacen"},
            {"name": "formal-action"},
            {"name": "priority-p0"},
            {"name": "owner-security"},
        ],
    }
    plan = build_plan({"items": [], "deferred_items": [source]}, [current])
    assert plan["operations"] == []
    assert plan["summary"]["total_operations"] == 0
