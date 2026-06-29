from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.validate_publication_sync import (
    _extract_frontend_asset_hash,
    _normalize_sha,
    _sha_matches,
    build_payload,
)


def test_sha_matches_accepts_short_prefix():
    assert _sha_matches("854d887f014e", "854d887f014ef70c90751bc422d139694fc4134d")


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
