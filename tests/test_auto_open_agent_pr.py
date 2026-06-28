from __future__ import annotations

from unittest.mock import MagicMock

from scripts.auto_open_agent_pr import build_body, is_permission_error, sync_existing_pr


def test_build_body_contains_increment_type():
    body = build_body("cursor/padrao-ouro-ciclos-88ba", "main")
    assert "increment-type: consolidate" in body
    assert "cursor/padrao-ouro-ciclos-88ba" in body
    assert "Padrão Ouro Delivery Automation" in body


def test_is_permission_error_detects_403():
    assert is_permission_error(RuntimeError('GitHub API PATCH /pulls/461 failed (403): {"message":"forbidden"}'))


def test_sync_existing_pr_ignora_403_quando_pr_ja_existe(tmp_path, monkeypatch):
    monkeypatch.setenv("PR_REQUEST_ARTIFACT_DIR", str(tmp_path))
    client = MagicMock()
    client.update_pr.side_effect = RuntimeError(
        'GitHub API PATCH /pulls/461 failed (403): {"message":"Resource not accessible by personal access token"}'
    )
    existing = {"number": 461, "html_url": "https://github.com/example/repo/pull/461"}

    exit_code = sync_existing_pr(
        client,
        existing,
        branch="cursor/consume-governance-cards-monitoramento-36e0",
        base="main",
        title="feat: teste",
        body="body",
    )

    assert exit_code == 0
    artifact = (tmp_path / "auto-pr-request.json").read_text(encoding="utf-8")
    assert "skipped_permission" in artifact
    assert "461" in artifact
