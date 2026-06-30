from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.validate_publication_sync import (
    _api_sha_acceptable,
    _extract_frontend_asset_hash,
    _normalize_sha,
    _sha_matches,
    build_payload,
)


def test_sha_matches_accepts_short_prefix():
    assert _sha_matches("854d887f014e", "854d887f014ef70c90751bc422d139694fc4134d")


def test_api_sha_acceptable_when_observed_matches_main_head(monkeypatch):
    monkeypatch.setattr(
        "scripts.validate_publication_sync._fetch_origin_main_sha",
        lambda: "0cfadcbcc348",
    )
    ok, reason = _api_sha_acceptable("723160b2c9ae", "0cfadcbcc3485fc42c3d4ad9d4a7f86279f0415f")
    assert ok is True
    assert reason == "matches_origin_main_head"


def test_api_sha_not_acceptable_when_observed_stale(monkeypatch):
    monkeypatch.setattr(
        "scripts.validate_publication_sync._fetch_origin_main_sha",
        lambda: "0cfadcbcc348",
    )
    ok, reason = _api_sha_acceptable("0cfadcbcc348", "723160b2c9ae")
    assert ok is False
    assert reason == "sha_mismatch"


def test_normalize_sha_handles_fly_image_ref():
    assert _normalize_sha("registry.fly.io/reqsys-api:deployment-854d887f014e") == "854d887f014e"


def test_extract_frontend_asset_hash():
    html = '<script type="module" src="/assets/index-BC6S1SXZ.js"></script>'
    assert _extract_frontend_asset_hash(html) == "BC6S1SXZ"


def test_build_payload_marks_unavailable_without_network(monkeypatch):
    def fake_validate_environment(env_name, cfg, *, expected_sha, expected_version, timeout):
        return {
            "environment": env_name,
            "api_url": cfg["api_url"],
            "frontend_url": cfg["frontend_url"],
            "expected": {"sha": expected_sha, "version": expected_version},
            "observed": {},
            "components": [],
            "operational_status": "unavailable",
            "synced": False,
            "blocking_issues": ["API indisponível"],
        }

    monkeypatch.setattr("scripts.validate_publication_sync.validate_environment", fake_validate_environment)
    payload = build_payload(
        manifest_path=ROOT / "infra" / "fly-environments.json",
        environment="prod",
        expected_sha="854d887f014e",
        expected_version="3.1.0",
        timeout=1.0,
    )
    assert payload["ok"] is False
    assert payload["blocking_issues"]
