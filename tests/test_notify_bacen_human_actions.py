from __future__ import annotations

from scripts.notify_bacen_human_actions import build_email, build_notification


def _plan(*, create: int, update: int, close: int, operations: list[dict]) -> dict:
    return {
        "contract": "reqsys-bacen-human-action-issue-sync",
        "summary": {
            "create": create,
            "update": update,
            "close": close,
            "total_operations": create + update + close,
        },
        "operations": operations,
        "approvals_fabricated": False,
        "production_touched": False,
    }


def test_no_change_does_not_notify() -> None:
    notification = build_notification(
        plan=_plan(create=0, update=0, close=0, operations=[]),
        repository="owner/repo",
        run_url="https://github.com/owner/repo/actions/runs/1",
        issues_url="https://github.com/owner/repo/issues?q=label%3Aformal-action",
    )

    assert notification["should_notify"] is False
    assert notification["actionable_controls"] == []
    assert notification["production_touched"] is False


def test_only_create_and_update_controls_are_notified_without_issue_body() -> None:
    notification = build_notification(
        plan=_plan(
            create=1,
            update=1,
            close=1,
            operations=[
                {
                    "action": "create",
                    "control_id": "BACEN-01",
                    "body": "Pessoa confidencial",
                },
                {
                    "action": "update",
                    "control_id": "BACEN-02",
                    "title": "Outro conteúdo não necessário",
                },
                {"action": "close", "control_id": "BACEN-03"},
            ],
        ),
        repository="owner/repo",
        run_url="https://github.com/owner/repo/actions/runs/2",
        issues_url="https://github.com/owner/repo/issues?q=label%3Aformal-action",
    )

    assert notification["should_notify"] is True
    assert notification["actionable_controls"] == ["BACEN-01", "BACEN-02"]
    assert "Pessoa confidencial" not in notification["text"]
    assert "Outro conteúdo" not in notification["text"]
    assert notification["approvals_fabricated"] is False
    assert notification["personal_assignees_fabricated"] is False
    assert notification["due_dates_fabricated"] is False


def test_email_is_action_notice_not_fabricated_approval() -> None:
    notification = build_notification(
        plan=_plan(
            create=0,
            update=1,
            close=0,
            operations=[{"action": "update", "control_id": "BACEN-08"}],
        ),
        repository="owner/repo",
        run_url="https://github.com/owner/repo/actions/runs/3",
        issues_url="https://github.com/owner/repo/issues?q=label%3Aformal-action",
    )

    message = build_email(
        sender="reqsys@example.invalid",
        recipient="owner@example.invalid",
        notification=notification,
    )
    plain = message.get_body(preferencelist=("plain",)).get_content()
    html = message.get_body(preferencelist=("html",)).get_content()
    body = plain + html

    assert "ações formais BACEN requerem atenção" in body
    assert "/approve" not in body
    assert "Nenhuma aprovação" in body
    assert "production_touched=false" in body
