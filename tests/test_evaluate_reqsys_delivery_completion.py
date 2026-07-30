from scripts.evaluate_reqsys_delivery_completion import evaluate


def matrix(statuses):
    return {
        "controls": [
            {
                "id": f"BACEN-{index:02d}",
                "status": status,
                "criticality": "critical",
                "owner": "GOVERNANCE",
                "next_stage": "real_formal_action",
                "evidence": f"artifacts/{index}.json",
                "production_touched": False,
            }
            for index, status in enumerate(statuses, start=1)
        ]
    }


def runtime(ok=True):
    return {
        "endpoints": [
            {"name": path, "ok": ok}
            for path in (
                "/health",
                "/api/runtime/health",
                "/api/runtime/readiness",
                "/api/runtime/liveness",
            )
        ]
    }


def test_formal_completion_when_technical_state_is_green_but_controls_are_partial():
    report = evaluate(
        matrix(["partial", "implemented"]),
        {"open_prs": [], "workflow_runs": []},
        runtime(),
    )
    assert report["phase"] == "FORMAL_COMPLETION"
    assert report["technical_ready"] is True
    assert report["formal_ready"] is False
    assert report["production_release_allowed"] is False
    assert report["human_authority_substitution_allowed"] is False


def test_technical_remediation_when_runtime_or_workflow_is_red():
    report = evaluate(
        matrix(["implemented"]),
        {
            "open_prs": [],
            "workflow_runs": [
                {"name": "required", "status": "completed", "conclusion": "failure"}
            ],
        },
        runtime(ok=False),
    )
    assert report["phase"] == "TECHNICAL_REMEDIATION"
    assert report["technical_ready"] is False
    assert report["delivered"] is False


def test_delivery_finalization_waits_for_open_non_draft_prs():
    report = evaluate(
        matrix(["implemented"]),
        {
            "open_prs": [{"number": 10, "state": "open", "draft": False}],
            "workflow_runs": [],
        },
        runtime(),
    )
    assert report["phase"] == "DELIVERY_FINALIZATION"
    assert report["formal_ready"] is True
    assert report["integration_ready"] is False


def test_delivered_requires_all_dimensions_green():
    report = evaluate(
        matrix(["implemented", "implemented"]),
        {"open_prs": [], "workflow_runs": []},
        runtime(),
    )
    assert report["phase"] == "DELIVERED"
    assert report["delivered"] is True
    assert report["production_release_allowed"] is True
    assert report["production_touched"] is False
