from datetime import datetime, timezone

from scripts.build_flow_completion_monitor import build_monitor


def definition():
    return {
        "flow": "delivery",
        "stale_after_hours": 24,
        "environments": [
            {"name": "dev", "order": 10, "stages": [{"name": "deploy", "order": 10}]},
            {"name": "stg", "order": 20, "stages": [{"name": "homologation", "order": 10}]},
            {"name": "prod", "order": 30, "stages": [{"name": "post-deploy-validation", "order": 10}]},
        ],
    }


def event(environment, stage, status="succeeded", sha="abc", evidence=True, updated_at="2026-07-20T12:00:00Z"):
    return {
        "environment": environment,
        "stage": stage,
        "status": status,
        "commit_sha": sha,
        "evidence_url": "https://github.com/evidence" if evidence else None,
        "updated_at": updated_at,
    }


def test_only_final_stage_with_matching_version_and_evidence_completes_flow():
    executions = [{
        "execution_id": "flow-1",
        "item_id": "PR-1",
        "expected_commit_sha": "abc",
        "events": [
            event("dev", "deploy"),
            event("stg", "homologation"),
            event("prod", "post-deploy-validation"),
        ],
    }]

    report = build_monitor(definition(), executions, datetime(2026, 7, 20, 13, tzinfo=timezone.utc))

    assert report["summary"]["completed"] == 1
    assert report["summary"]["open"] == 0
    assert report["items"][0]["status"] == "COMPLETED"


def test_missing_prod_validation_keeps_item_open_and_points_next_stage():
    executions = [{
        "execution_id": "flow-2",
        "item_id": "PR-2",
        "expected_commit_sha": "abc",
        "events": [event("dev", "deploy"), event("stg", "homologation")],
    }]

    report = build_monitor(definition(), executions, datetime(2026, 7, 20, 13, tzinfo=timezone.utc))
    item = report["open_items"][0]

    assert item["completed"] is False
    assert item["last_completed"] == {"environment": "stg", "stage": "homologation"}
    assert item["next_expected"] == {"environment": "prod", "stage": "post-deploy-validation"}


def test_failed_stage_and_version_drift_do_not_complete():
    executions = [
        {
            "execution_id": "flow-3",
            "item_id": "PR-3",
            "expected_commit_sha": "abc",
            "events": [event("dev", "deploy"), event("stg", "homologation", status="failed")],
        },
        {
            "execution_id": "flow-4",
            "item_id": "PR-4",
            "expected_commit_sha": "abc",
            "events": [
                event("dev", "deploy"),
                event("stg", "homologation"),
                event("prod", "post-deploy-validation", sha="old"),
            ],
        },
    ]

    report = build_monitor(definition(), executions, datetime(2026, 7, 20, 13, tzinfo=timezone.utc))

    assert report["summary"]["failed"] == 1
    assert report["summary"]["open"] == 2
    assert all(not item["completed"] for item in report["items"])
