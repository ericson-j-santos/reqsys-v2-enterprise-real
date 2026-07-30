from scripts.plan_bacen_human_action_issue_sync import build_plan, body_for, title_for


def item(control_id="BACEN-08", status="partial"):
    return {
        "control_id": control_id,
        "title": "Responsável executivo e relatório anual",
        "status": status,
        "priority": "P0",
        "responsible_role": "GOVERNANCE",
        "required_action": "formal_designation_and_signed_report",
        "evidence_reference": "artifacts/bacen/bacen-08.json",
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
            {"name": "owner-governance"},
        ],
    }


def test_creates_issue_for_new_pending_control():
    plan = build_plan({"items": [item()]}, [])
    assert plan["summary"] == {
        "create": 1,
        "update": 0,
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
