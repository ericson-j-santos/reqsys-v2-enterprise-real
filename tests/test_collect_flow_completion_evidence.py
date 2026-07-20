from scripts.collect_flow_completion_evidence import normalize


def test_normalizes_ci_fly_and_prod_health_for_same_sha():
    sha = "abc123"
    runs = {
        "workflow_runs": [
            {
                "id": 10,
                "name": "CI ReqSys v2 Enterprise",
                "head_sha": sha,
                "conclusion": "success",
                "html_url": "https://github.test/runs/10",
                "updated_at": "2026-07-20T10:00:00Z",
            },
            {
                "id": 11,
                "name": "Fly Environment Homologation Gate",
                "head_sha": sha,
                "conclusion": "success",
                "html_url": "https://github.test/runs/11",
                "updated_at": "2026-07-20T11:00:00Z",
            },
        ]
    }
    artifacts = {
        "artifacts": [
            {"workflow_run_id": 11, "name": "fly-homologation-dev", "archive_download_url": "https://github.test/artifacts/dev"},
            {"workflow_run_id": 11, "name": "fly-homologation-stg", "archive_download_url": "https://github.test/artifacts/stg"},
            {"workflow_run_id": 11, "name": "fly-homologation-prod", "archive_download_url": "https://github.test/artifacts/prod"},
        ]
    }
    health = {
        "commit_sha": sha,
        "run_id": 12,
        "observed_at": "2026-07-20T12:00:00Z",
        "evidence_url": "https://reqsys-api.fly.dev/health",
        "checks": [{"url": "/health", "healthy": True}, {"url": "/api/runtime/readiness", "healthy": True}],
    }

    executions = normalize(runs, artifacts, health)

    assert len(executions) == 1
    stages = {(item["environment"], item["stage"], item["status"]) for item in executions[0]["events"]}
    assert ("dev", "build", "succeeded") in stages
    assert ("dev", "smoke-test", "succeeded") in stages
    assert ("stg", "homologation", "succeeded") in stages
    assert ("prod", "deploy", "succeeded") in stages
    assert ("prod", "post-deploy-validation", "succeeded") in stages


def test_failed_health_keeps_final_validation_failed():
    executions = normalize(
        {"workflow_runs": []},
        {"artifacts": []},
        {
            "commit_sha": "def456",
            "observed_at": "2026-07-20T12:00:00Z",
            "evidence_url": "https://reqsys-api.fly.dev/health",
            "checks": [{"url": "/health", "healthy": True}, {"url": "/api/runtime/readiness", "healthy": False}],
        },
    )

    final_event = next(item for item in executions[0]["events"] if item["stage"] == "post-deploy-validation")
    assert final_event["status"] == "failed"


def test_ignores_unknown_artifact_names():
    executions = normalize(
        {"workflow_runs": [{"id": 50, "name": "Fly Environment Homologation Gate", "head_sha": "xyz", "conclusion": "success"}]},
        {"artifacts": [{"workflow_run_id": 50, "name": "other-artifact"}]},
        {},
    )

    assert executions[0]["events"] == []
