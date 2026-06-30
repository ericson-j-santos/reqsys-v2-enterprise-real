from __future__ import annotations

from scripts.verify_deploy_build_sha import normalize_sha, verify_deploy_build_sha


def test_normalize_sha_short_prefix():
    assert normalize_sha("ccd026a100c1331e55876c785a3d041defebc16c") == "ccd026a100c1"


def test_verify_deploy_build_sha_matches(monkeypatch):
    calls = {"count": 0}

    def fake_fetch(base_url: str, timeout: float):
        calls["count"] += 1
        return {"build_sha": "ccd026a100c1"}, None

    monkeypatch.setattr("scripts.verify_deploy_build_sha.fetch_build_info", fake_fetch)
    report = verify_deploy_build_sha(
        base_url="https://example.test",
        expected_sha="ccd026a100c1",
        timeout=1.0,
        max_attempts=3,
        delay_seconds=0.0,
    )
    assert report["ok"] is True
    assert calls["count"] == 1


def test_verify_deploy_build_sha_retries_until_match(monkeypatch):
    sequence = [
        ({"build_sha": "238d1f47caea"}, None),
        ({"build_sha": "ccd026a100c1"}, None),
    ]

    def fake_fetch(base_url: str, timeout: float):
        return sequence.pop(0)

    monkeypatch.setattr("scripts.verify_deploy_build_sha.fetch_build_info", fake_fetch)
    report = verify_deploy_build_sha(
        base_url="https://example.test",
        expected_sha="ccd026a100c1",
        timeout=1.0,
        max_attempts=3,
        delay_seconds=0.0,
    )
    assert report["ok"] is True
    assert report["attempts"] == 2
