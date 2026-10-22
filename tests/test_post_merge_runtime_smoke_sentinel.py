from __future__ import annotations

from dataclasses import asdict

from scripts.post_merge_runtime_smoke_sentinel import (
    EXPECTED_ARTIFACT_NAME,
    EXPECTED_JOB_NAME,
    EXPECTED_REPOSITORY,
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
            "html_url": "https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions/runs/123",
        }
    }


def _runtime_evidence(expected_sha: str = SHA) -> dict:
    return {
        "environment": "dev",
        "base_url_kind": "signed_locator",
        "expected_sha": expected_sha,
        "observed_sha": expected_sha,
        "final_observed_sha": expected_sha,
        "build_sha_matches_expected": True,
        "/api/health": {"http": 200},
        "/api/runtime/health": {"http": 200},
        "/api/runtime/readiness": {"http": 200},
        "/api/runtime/build-info": {"http": 200},
        "frontend": {
            "mode": "static_nginx",
            "http": 200,
            "vite_client_http": 404,
            "asset_http": 200,
        },
    }


def _evaluate_with_evidence(event=None, evidence=None, **transport_options):
    return evaluate_event(
        _event() if event is None else event,
        repo=EXPECTED_REPOSITORY,
        token="token",
        request_json=_transport(**transport_options),
        upstream_evidence=_runtime_evidence() if evidence is None else evidence,
    )


def _transport(
    *,
    artifact_name: str = EXPECTED_ARTIFACT_NAME,
    artifact_size: int = 100,
    artifact_expired: bool = False,
    duplicate_artifact: bool = False,
    step_override: dict[str, str] | None = None,
    main_sha: str = SHA,
    job_conclusion: str = "success",
):
    def fake_request_json(url: str, token: str) -> dict:
        assert token == "token"
        assert url.startswith("https://api.github.com/repos/ericson-j-santos/reqsys-v2-enterprise-real/")
        if url.endswith("/actions/runs/123/artifacts?per_page=100"):
            artifacts = [{
                "name": artifact_name,
                "size_in_bytes": artifact_size,
                "expired": artifact_expired,
            }]
            if duplicate_artifact:
                artifacts.append(dict(artifacts[0]))
            return {
                "artifacts": artifacts
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
    return _evaluate_with_evidence(event=event, **transport_options)


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


def test_rerun_accepts_multiple_valid_artifacts_with_the_same_name():
    result = _evaluate(duplicate_artifact=True)
    assert result.status == "ready"
    assert result.blocking_issues == []
    assert result.artifacts == [EXPECTED_ARTIFACT_NAME, EXPECTED_ARTIFACT_NAME]


def test_runtime_artifact_value_not_equal_current_sha_blocks():
    payload = _runtime_evidence()
    payload["observed_sha"] = OTHER_SHA
    payload["final_observed_sha"] = OTHER_SHA
    payload["build_sha_matches_expected"] = False
    result = _evaluate_with_evidence(evidence=payload)
    assert result.status == "blocked"
    assert "runtime_evidence_contract_failed" in result.blocking_issues
    assert result.runtime_observed_sha == OTHER_SHA


def test_runtime_artifact_health_and_frontend_checks_must_have_executed():
    for mutation in ("health", "frontend", "sha"):
        payload = _runtime_evidence()
        if mutation == "health":
            payload["/api/runtime/readiness"]["http"] = 503
        elif mutation == "frontend":
            payload["frontend"]["vite_client_http"] = 200
        else:
            payload["expected_sha"] = OTHER_SHA
        result = _evaluate_with_evidence(evidence=payload)
        assert result.status == "blocked"
        assert not result.runtime_evidence_verified


def test_runtime_artifact_missing_blocks_even_when_source_passed():
    result = evaluate_event(
        _event(),
        repo=EXPECTED_REPOSITORY,
        token="token",
        request_json=_transport(),
        upstream_evidence=None,
    )
    assert result.status == "blocked"
    assert "runtime_evidence_missing" in result.blocking_issues


def test_runtime_artifact_local_reader_rejects_duplicates_and_non_json(tmp_path):
    from scripts.post_merge_runtime_smoke_sentinel import _load_runtime_evidence
    (tmp_path / "pc24x7-dev").mkdir()
    root = tmp_path / "pc24x7-dev" / "runtime-smoke.json"
    root.write_text("not json", encoding="utf-8")
    assert _load_runtime_evidence(tmp_path) is None
    import json
    root.write_text(json.dumps(_runtime_evidence()), encoding="utf-8")
    assert _load_runtime_evidence(tmp_path)["observed_sha"] == SHA
    (tmp_path / "extra").mkdir()
    (tmp_path / "extra" / "runtime-smoke.json").write_text(root.read_text(encoding="utf-8"), encoding="utf-8")
    assert _load_runtime_evidence(tmp_path) is None


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


def test_untrusted_repository_cannot_redirect_github_api_requests():
    def never_called(url: str, token: str) -> dict:
        raise AssertionError("untrusted repo must be rejected before I/O")
    result = evaluate_event(
        _event(),
        repo="other-owner/other-repo",
        token="token",
        request_json=never_called,
    )
    assert result.status == "blocked"
    assert "repository_not_allowed" in result.blocking_issues


def test_missing_token_blocks_real_evidence_validation():
    result = evaluate_event(_event(), repo=EXPECTED_REPOSITORY, token=None)
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
    assert "actions/download-artifact@" in pipeline
    assert "github.event.workflow_run.event == 'push'" in pipeline
    assert "--upstream-evidence-dir artifacts/upstream-public-dev" in pipeline
    assert all(name in active for name in REQUIRED_STEPS)
    assert "build_sha_mismatch" in active
    assert "runtime-smoke.json" in active
    assert "if: ${{ false }}" in retired
    assert EXPECTED_WORKFLOW_NAME not in retired


def test_http_transport_exception_blocks_and_does_not_claim_sentinel_ready():
    def failed_transport(url: str, token: str) -> dict:
        raise RuntimeError("connection unavailable")
    result = evaluate_event(_event(), repo=EXPECTED_REPOSITORY, token="token", request_json=failed_transport)
    assert result.status == "blocked"
    assert "github_read_unavailable" in result.blocking_issues

