from scripts.collect_flow_completion_evidence import normalize


def test_normalizes_ci_and_explicit_historical_offline_fly_evidence():
    sha = "abc123"
    runs = {
        "historical": True,
        "offline": True,
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
                "historical": True,
                "offline": True,
                "html_url": "https://github.test/runs/11",
                "updated_at": "2026-07-20T11:00:00Z",
            },
        ],
    }
    artifacts = {
        "historical": True,
        "offline": True,
        "artifacts": [
            {"workflow_run_id": 11, "name": "fly-homologation-dev", "archive_download_url": "https://github.test/artifacts/dev"},
            {"workflow_run_id": 11, "name": "fly-homologation-stg", "archive_download_url": "https://github.test/artifacts/stg"},
            {"workflow_run_id": 11, "name": "fly-homologation-prod", "archive_download_url": "https://github.test/artifacts/prod"},
        ],
    }
    health = {
        "commit_sha": sha,
        "run_id": 12,
        "observed_at": "2026-07-20T12:00:00Z",
        "evidence_url": "https://reqsys-api.fly.dev/health",
        "historical": True,
        "offline": True,
        "checks": [{"url": "/health", "healthy": True}, {"url": "/api/runtime/readiness", "healthy": True}],
    }

    executions = normalize(runs, artifacts, health, include_historical_offline=True)

    assert len(executions) == 1
    events = executions[0]["events"]
    stages = {(item["environment"], item["stage"], item["status"]) for item in events}
    assert ("dev", "build", "succeeded") in stages
    assert ("dev", "smoke-test", "succeeded") in stages
    assert ("stg", "homologation", "succeeded") in stages
    assert ("prod", "deploy", "succeeded") in stages
    assert ("prod", "post-deploy-validation", "succeeded") in stages
    assert all(item.get("classification") == "historical_offline" for item in events if item["stage"] != "build")


def test_ignores_fly_evidence_without_explicit_offline_opt_in():
    executions = normalize(
        {"workflow_runs": [{"id": 1, "name": "Fly Environment Homologation Gate", "head_sha": "abc"}]},
        {"artifacts": [{"workflow_run_id": 1, "name": "fly-homologation-dev"}]},
        {},
    )
    assert executions[0]["events"] == []


def test_ignores_fly_io_health_variant_without_explicit_offline_opt_in():
    executions = normalize(
        {"workflow_runs": []},
        {"artifacts": []},
        {
            "commit_sha": "retired-provider",
            "evidence_url": "https://API.FLY.IO./health",
            "checks": [{"url": "/health", "healthy": True}],
        },
    )

    assert executions == []


def test_failed_neutral_health_keeps_final_validation_failed():
    executions = normalize(
        {"workflow_runs": []},
        {"artifacts": []},
        {
            "commit_sha": "def456",
            "observed_at": "2026-07-20T12:00:00Z",
            "evidence_url": "https://api.example.net/health",
            "checks": [{"url": "/health", "healthy": True}, {"url": "/api/runtime/readiness", "healthy": False}],
        },
    )
    final_event = next(item for item in executions[0]["events"] if item["stage"] == "post-deploy-validation")
    assert final_event["status"] == "failed"


def test_ignores_unknown_artifact_names():
    executions = normalize(
        {"workflow_runs": [{"id": 50, "name": "Fly Environment Homologation Gate", "head_sha": "xyz", "historical": True, "offline": True}], "historical": True, "offline": True},
        {"artifacts": [{"workflow_run_id": 50, "name": "other-artifact"}], "historical": True, "offline": True},
        {},
        include_historical_offline=True,
    )
    assert executions[0]["events"] == []
