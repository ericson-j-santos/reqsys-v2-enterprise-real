from scripts.todo_event_relay_snapshot import build_snapshot, clean_title


def test_clean_title_removes_html():
    assert clean_title("<p>Hello&nbsp;World</p>", "x") == "Hello World"


def test_snapshot_is_normalized_and_contains_no_secret_fields():
    teams = [
        {
            "id": "1789640711094",
            "createdDateTime": "2026-09-17T10:25:11.094Z",
            "body": {"content": "<p>ReqSys Teams</p>"},
        }
    ]
    gitlab = [
        {
            "id": "2eb38c8cdd17ff140126d3d7f82f587ea3e59d41",
            "title": "merge real",
            "committed_date": "2026-09-17T08:08:48-03:00",
        }
    ]
    snapshot = build_snapshot(teams, gitlab, generated_at="2026-09-17T11:00:00+00:00")
    assert snapshot["contract"] == "todo-event-relay-snapshot-v1"
    assert snapshot["source_counts"] == {"teams": 1, "gitlab": 1}
    assert snapshot["secret_values_persisted"] is False
    assert {item["source"] for item in snapshot["items"]} == {"teams", "gitlab"}
    serialized = str(snapshot).casefold()
    assert "access_token" not in serialized
    assert "client_secret" not in serialized
    assert "private-token" not in serialized


def test_snapshot_deduplicates_same_external_item():
    teams = [
        {"id": "1", "createdDateTime": "2026-09-17T10:00:00Z", "body": {"content": "a"}},
        {"id": "1", "createdDateTime": "2026-09-17T10:00:00Z", "body": {"content": "a"}},
    ]
    snapshot = build_snapshot(teams, [], generated_at="2026-09-17T11:00:00+00:00")
    assert len(snapshot["items"]) == 1
    assert snapshot["items"][0]["external_id"] == "message-1"
