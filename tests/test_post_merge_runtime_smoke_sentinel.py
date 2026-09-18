from __future__ import annotations

from scripts.post_merge_runtime_smoke_sentinel import evaluate_event, render_summary


def _event(conclusion: str = "success", branch: str = "main") -> dict:
    return {
        "workflow_run": {
            "id": 123,
            "name": "Runtime Production Smoke Governed",
            "head_branch": branch,
            "conclusion": conclusion,
            "html_url": "https://github.com/example/repo/actions/runs/123",
        }
    }


def test_evaluate_event_ready_when_workflow_succeeded_and_artifact_exists() -> None:
    def fake_request_json(url: str, token: str) -> dict:
        assert "actions/runs/123/artifacts" in url
        assert token == "token"
        return {"artifacts": [{"name": "runtime-production-smoke-governed"}]}

    result = evaluate_event(_event(), repo="example/repo", token="token", request_json=fake_request_json)

    assert result.status == "ready"
    assert result.blocking_issues == []
    assert result.artifacts == ["runtime-production-smoke-governed"]


def test_evaluate_event_blocks_when_artifact_is_missing() -> None:
    result = evaluate_event(
        _event(),
        repo="example/repo",
        token="token",
        request_json=lambda _url, _token: {"artifacts": [{"name": "other"}]},
    )

    assert result.status == "blocked"
    assert "artifact_missing" in result.blocking_issues


def test_evaluate_event_blocks_when_workflow_failed() -> None:
    result = evaluate_event(
        _event(conclusion="failure"),
        repo="example/repo",
        token="token",
        request_json=lambda _url, _token: {"artifacts": [{"name": "runtime-production-smoke-governed"}]},
    )

    assert result.status == "blocked"
    assert "workflow_failed" in result.blocking_issues


def test_evaluate_event_blocks_wrong_branch() -> None:
    result = evaluate_event(
        _event(branch="feature/test"),
        repo="example/repo",
        token="token",
        request_json=lambda _url, _token: {"artifacts": [{"name": "runtime-production-smoke-governed"}]},
    )

    assert result.status == "blocked"
    assert "wrong_branch" in result.blocking_issues


def test_render_summary_exposes_operational_contract() -> None:
    result = evaluate_event(
        _event(),
        repo="example/repo",
        token="token",
        request_json=lambda _url, _token: {"artifacts": [{"name": "runtime-production-smoke-governed"}]},
    )

    summary = render_summary(result)

    assert "Post-merge Runtime Smoke Sentinel" in summary
    assert "runtime-production-smoke-governed" in summary
    assert "ready" in summary
