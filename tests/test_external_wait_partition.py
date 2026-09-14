from scripts.external_wait_partition import MARKER, build_wait_partition, enrich_report


def comment(comment_id, created_at, payload):
    import json
    return {
        "id": comment_id,
        "html_url": f"https://github.example/issues/1#issuecomment-{comment_id}",
        "created_at": created_at,
        "body": f"{MARKER}\n```json\n{json.dumps(payload)}\n```",
    }


def event(event_id, wait_id, action, category="permission_admin", correlation_id="corr-1"):
    return {
        "event_id": event_id,
        "wait_id": wait_id,
        "action": action,
        "category": category,
        "correlation_id": correlation_id,
        "sha": "abc123",
        "source_reference": "issue:1683",
    }


def test_closed_wait_is_measured_from_github_comment_timestamps():
    comments = [
        comment(10, "2026-09-14T10:00:00Z", event("evt-1", "wait-1", "blocked")),
        comment(11, "2026-09-14T10:25:30Z", event("evt-2", "wait-1", "unblocked")),
    ]
    partition = build_wait_partition(comments)
    assert partition["external_wait_status"] == "instrumented"
    assert partition["external_blocked_minutes"] == 25.5
    assert partition["closed_waits"] == 1
    assert partition["open_waits"] == 0
    assert partition["by_category"]["permission_admin"] == 25.5
    assert partition["waits"][0]["blocked_source"]["comment_id"] == 10
    assert partition["waits"][0]["unblocked_source"]["comment_id"] == 11


def test_open_wait_does_not_invent_unblocked_at_or_running_duration():
    comments = [
        comment(20, "2026-09-14T11:00:00Z", event("evt-3", "wait-2", "blocked", "external_provider")),
    ]
    partition = build_wait_partition(comments)
    assert partition["external_wait_status"] == "partial"
    assert partition["external_blocked_minutes"] == 0.0
    assert partition["open_waits"] == 1
    assert partition["waits"][0]["unblocked_at"] is None
    assert partition["waits"][0]["duration_minutes"] is None


def test_duplicate_reprocessing_is_idempotent():
    payload = event("evt-4", "wait-3", "blocked")
    comments = [
        comment(30, "2026-09-14T12:00:00Z", payload),
        comment(31, "2026-09-14T12:00:01Z", payload),
        comment(32, "2026-09-14T12:05:00Z", event("evt-5", "wait-3", "unblocked")),
    ]
    partition = build_wait_partition(comments)
    assert partition["external_blocked_minutes"] == 5.0
    assert partition["duplicate_event_count"] == 1
    assert partition["closed_waits"] == 1


def test_semantic_duplicate_with_new_event_id_is_not_double_counted():
    comments = [
        comment(40, "2026-09-14T13:00:00Z", event("evt-6", "wait-4", "blocked")),
        comment(41, "2026-09-14T13:01:00Z", event("evt-7", "wait-4", "blocked")),
        comment(42, "2026-09-14T13:10:00Z", event("evt-8", "wait-4", "unblocked")),
    ]
    partition = build_wait_partition(comments)
    assert partition["external_blocked_minutes"] == 10.0
    assert partition["duplicate_event_count"] == 1


def test_free_text_and_invalid_structured_event_do_not_create_wait():
    comments = [
        {
            "id": 50,
            "created_at": "2026-09-14T14:00:00Z",
            "html_url": "https://github.example/issues/1#issuecomment-50",
            "body": "Estamos aguardando aprovação administrativa desde cedo.",
        },
        {
            "id": 51,
            "created_at": "2026-09-14T14:01:00Z",
            "html_url": "https://github.example/issues/1#issuecomment-51",
            "body": f"{MARKER}\n```json\n{{\"event_id\":\"evt-invalid\",\"action\":\"blocked\"}}\n```",
        },
    ]
    partition = build_wait_partition(comments)
    assert partition["external_blocked_minutes"] == 0.0
    assert partition["invalid_event_count"] == 1
    assert partition["waits"] == []


def test_collection_failure_is_explicit_and_never_returns_zero_as_fact():
    partition = build_wait_partition([], {"ok": False, "error": "github_api_timeout"})
    assert partition["external_wait_status"] == "collection_failed"
    assert partition["external_blocked_minutes"] is None
    assert partition["collection_error"] == "github_api_timeout"


def test_report_integration_replaces_placeholder_wait_partition():
    report = {
        "schema_version": "1.2.0",
        "delivery_velocity": {
            "wait_partition": {
                "technical_intervals_instrumented": True,
                "external_blocked_minutes": None,
                "external_wait_status": "not_instrumented",
            }
        },
    }
    comments = [
        comment(60, "2026-09-14T15:00:00Z", event("evt-9", "wait-5", "blocked", "human_gate")),
        comment(61, "2026-09-14T15:07:00Z", event("evt-10", "wait-5", "unblocked", "human_gate")),
    ]
    enriched = enrich_report(report, comments)
    assert enriched["schema_version"] == "1.3.0"
    assert enriched["delivery_velocity"]["wait_partition"]["external_blocked_minutes"] == 7.0
    assert enriched["delivery_velocity"]["wait_partition"]["by_category"]["human_gate"] == 7.0


def test_evaluator_workflow_collects_ledger_with_bounded_pagination():
    from pathlib import Path
    workflow = Path(".github/workflows/reqsys-next-increment-auto-evaluation.yml").read_text(encoding="utf-8")
    assert "issues: read" in workflow
    assert "LEDGER_ISSUE: '1683'" in workflow
    assert "COMMENT_MAX_PAGES: '3'" in workflow
    assert "external_wait_partition.py" in workflow
    assert "external-wait-collection-status.json" in workflow


def test_recorder_workflow_is_structured_and_verifies_persistence():
    from pathlib import Path
    workflow = Path(".github/workflows/reqsys-external-wait-recorder.yml").read_text(encoding="utf-8")
    assert "issues: write" in workflow
    assert "reqsys-external-wait-event:v1" in workflow
    assert "Verify persisted event independently" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "COMMENT_MAX_PAGES: \"3\"" in workflow
