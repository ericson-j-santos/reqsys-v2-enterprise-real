from __future__ import annotations

from dataclasses import asdict

from scripts.post_merge_runtime_smoke_sentinel import (
    EXPECTED_ARTIFACT_NAME,
    EXPECTED_JOB_NAME,
    EXPECTED_WORKFLOW_ID,
    EXPECTED_WORKFLOW_NAME,
    REQUIRED_STEPS,
    evaluate_event,
    render_summary,
)

SHA = "a" * 40
OTHER_SHA = "b" * 40


def _event(
    *,
    conclusion: str = "success",
    branch: str = "main",
    source_event: str = "push",
    source_sha: str = SHA,
    name: str = EXPECTED_WORKFLOW_NAME,
    workflow_id: int = EXPECTED_WORKFLOW_ID,
) -> dict:
    return {
        "workflow_run": {
            "id": 123,
            "workflow_id": workflow_id,
            "name": name,
            "head_branch": branch,
            "head_sha": source_sha,
            "event": source_event,
            "conclusion": conclusion,
            "html_url": "https://github.com/example/repo/actions/runs/123",
        }
    }


def _transport(
    *,
    artifact_name: str = EXPECTED_ARTIFACT_NAME,
    artifact_size: int = 100,
    artifact_expired: bool = False,
    step_override: dict[str, str] | None = None,
    main_sha: str = SHA,
    job_conclusion: str = "success",
):
    def fake_request_json(url: str, token: str) -> dict:
        assert token == "token"
        assert url.startswith("https://api.github.com/repos/example/repo/")
        if url.endswith("/actions/runs/123/artifacts?per_page=100"):
            return {
                "artifacts": [{
                    "name": artifact_name,
                    "size_in_bytes": artifact_size,
                    "expired": artifact_expired,
                }]
            }
        if url.endswith("/actions/runs/123/jobs?per_page=100"):
            return {
                "jobs": [{
                    "name": EXPECTED_JOB_NAME,
                    "status": "completed",
                    "conclusion": job_conclusion,
                    "steps": [
                        {
                            "name": name,
                            "status": "completed",
                            "conclusion": (step_override or {}).get(name, "success"),
                        }
                        for name in sorted(REQUIRED_STEPS)
                    ],
                }]
            }
        if url.endswith("/branches/main"):
            return {"commit": {"sha": main_sha}}
        raise AssertionError(url)
    return fake_request_json


def _evaluate(event=None, **transport_options):
    return evaluate_event(
        _event() if event is None else event,
        repo="example/repo",
        token="token",
        request_json=_transport(**transport_options),
    )


def test_real_runtime_source_accepts_matching_main_and_executed_steps():
    result = _evaluate()
    assert result.status == "ready"
    assert result.blocking_issues == []
    assert result.artifacts == [EXPECTED_ARTIFACT_NAME]
    assert result.source_sha == result.main_sha == SHA
    assert result.required_steps_verified is True


def test_repeated_same_evidence_is_idempotent():
    first = asdict(_evaluate())
    second = asdict(_evaluate())
    first.pop("generated_at")
    second.pop("generated_at")
    assert first == second


def test_missing_artifact_blocks():
    result = _evaluate(artifact_name="unrelated")
    assert result.status == "blocked"
    assert "artifact_missing_or_invalid" in result.blocking_issues


def test_expired_or_empty_artifact_blocks():
    for options in ({"artifact_expired": True}, {"artifact_size": 0}):
        result = _evaluate(**options)
        assert result.status == "blocked"
        assert "artifact_missing_or_invalid" in result.blocking_issues


def test_skipped_or_failed_source_never_passes():
    for conclusion in ("skipped", "failure", "cancelled"):
        result = _evaluate(event=_event(conclusion=conclusion))
        assert result.status == "blocked"
        assert "workflow_failed" in result.blocking_issues


def test_wrong_source_identity_is_rejected():
    for changed in (
        {"name": "Runtime Production Smoke Governed"},
        {"workflow_id": 0},
        {"branch": "feature/test"},
        {"source_event": "workflow_dispatch"},
        {"source_event": "pull_request"},
        {"source_sha": "invalid"},
    ):
        result = _evaluate(event=_event(**changed))
        assert result.status == "blocked"


def test_current_main_sha_drift_blocks_without_spoofed_success():
    result = _evaluate(main_sha=OTHER_SHA)
    assert result.status == "blocked"
    assert "published_run_not_current_main_sha" in result.blocking_issues


def test_skipped_required_step_blocks_even_if_source_workflow_is_green():
    step_name = "Validar runtime DEV real com política de SHA por escopo"
    result = _evaluate(step_override={step_name: "skipped"})
    assert result.status == "blocked"
    assert "required_steps_not_executed" in result.blocking_issues


def test_job_failure_blocks_even_if_workflow_conclusion_is_green():
    result = _evaluate(job_conclusion="failure")
    assert result.status == "blocked"
    assert "required_steps_not_executed" in result.blocking_issues


def test_missing_token_blocks_real_evidence_validation():
    result = evaluate_event(_event(), repo="example/repo", token=None)
    assert result.status == "blocked"
    assert "github_provenance_unavailable" in result.blocking_issues


def test_summary_includes_runtime_source_sha_and_failed_readiness():
    result = _evaluate(main_sha=OTHER_SHA)
    summary = render_summary(result)
    assert "Post-merge Runtime Smoke Sentinel" in summary
    assert EXPECTED_ARTIFACT_NAME in summary
    assert "blocked" in summary
    assert SHA in summary
    assert OTHER_SHA in summary


def test_workflow_targets_active_dev_source_instead_of_retired_fly():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    pipeline = (root / ".github/workflows/post-merge-runtime-smoke-sentinel.yml").read_text(encoding="utf-8")
    active = (root / ".github/workflows/validacao-acessos.yml").read_text(encoding="utf-8")
    retired = (root / ".github/workflows/runtime-production-smoke-governed.yml").read_text(encoding="utf-8")
    assert f'workflows: ["{EXPECTED_WORKFLOW_NAME}"]' in pipeline
    assert EXPECTED_JOB_NAME in active
    assert all(name in active for name in REQUIRED_STEPS)
    assert "build_sha_mismatch" in active
    assert "runtime-smoke.json" in active
    assert "if: ${{ false }}" in retired
    assert EXPECTED_WORKFLOW_NAME not in retired


def test_http_transport_exception_blocks_and_does_not_claim_sentinel_ready():
    def failed_transport(url: str, token: str) -> dict:
        raise RuntimeError("connection unavailable")
    result = evaluate_event(_event(), repo="example/repo", token="token", request_json=failed_transport)
    assert result.status == "blocked"
    assert "github_read_unavailable" in result.blocking_issues
