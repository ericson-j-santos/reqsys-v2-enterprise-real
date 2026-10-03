from scripts.environment_drift_analyzer import analyze


def test_unmarked_legacy_url_drift_does_not_create_active_recommendation():
    report = analyze(
        {
            "environments": [{"canonical": "dev", "status": "ready", "url_matrix_aligned": False}],
            "summary": {"promotion_order": ["dev"]},
        },
        "abc123",
    )
    assert report["classification"] == "current_provider_neutral"
    assert report["findings"] == []
    assert all("fly" not in item.lower() for item in report["recommendations"])


def test_explicit_historical_offline_drift_is_reported_as_archive_context():
    report = analyze(
        {
            "historical": True,
            "offline": True,
            "environments": [{"canonical": "dev", "status": "ready", "url_matrix_aligned": False}],
            "summary": {"promotion_order": ["dev"]},
        },
        "abc123",
    )
    assert report["classification"] == "historical_offline"
    assert report["findings"][0]["type"] == "historical_offline_url_matrix_drift"
    assert "histórico" in report["recommendations"][0]
