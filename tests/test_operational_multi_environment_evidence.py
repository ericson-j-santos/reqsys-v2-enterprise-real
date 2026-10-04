import pytest

from scripts.operational_multi_environment_evidence import build_env_entry, consolidate


def test_build_env_entry_uses_provider_neutral_probe_data():
    probe = {
        "name": "desenvolvimento",
        "frontend": "https://app-dev.example.net",
        "api": "https://api-dev.example.net/docs",
        "status": "ready",
    }
    entry = build_env_entry("dev", probe)
    assert entry["canonical"] == "dev"
    assert entry["frontend_url"] == "https://app-dev.example.net"
    assert "fly_api_url" not in entry
    assert "url_matrix_aligned" not in entry


def test_historical_matrix_is_attached_only_as_offline_reference():
    report = consolidate(
        {"environments": [{"canonical": "dev", "status": "ready"}], "summary": {}},
        "abc123",
        historical_offline_fly_matrix={
            "historical": True,
            "offline": True,
            "environments": {"dev": {"api_url": "https://legacy.fly.dev"}},
        },
    )
    assert report["historical_offline_reference"]["classification"] == "historical_offline"
    assert report["environments"][0]["canonical"] == "dev"
    assert "fly_api_url" not in report["environments"][0]


def test_unmarked_legacy_matrix_is_rejected():
    with pytest.raises(ValueError, match="historical=true e offline=true"):
        consolidate(
            {"environments": []},
            "abc123",
            historical_offline_fly_matrix={"environments": {"dev": {}}},
        )
