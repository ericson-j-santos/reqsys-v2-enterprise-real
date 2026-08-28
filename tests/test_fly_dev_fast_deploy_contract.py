from pathlib import Path


WORKFLOW = Path(".github/workflows/fly-dev-fast-deploy.yml")


def text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_fast_deploy_is_dev_only_and_cancels_obsolete_runs() -> None:
    workflow = text()

    assert "name: Fly DEV Fast Deploy" in workflow
    assert "group: fly-dev-fast-deploy" in workflow
    assert "cancel-in-progress: true" in workflow
    assert "environment: dev" in workflow
    assert "production" not in workflow.lower()
    assert "APROVO-PROD" not in workflow


def test_api_and_frontend_are_independent_parallel_jobs() -> None:
    workflow = text()
    api = workflow.split("\n  deploy-api:\n", 1)[1].split("\n  deploy-frontend:\n", 1)[0]
    frontend = workflow.split("\n  deploy-frontend:\n", 1)[1].split("\n  smoke:\n", 1)[0]

    assert "needs: preflight" in api
    assert "needs: preflight" in frontend
    assert "deploy-frontend" not in api
    assert "deploy-api" not in frontend


def test_dev_deploy_removes_known_waits_and_duplicate_restart() -> None:
    workflow = text()

    assert "flyctl secrets set ALLOW_DEMO_LOGIN=true --stage" in workflow
    assert "--strategy immediate" in workflow
    assert "--deploy-retries 2" in workflow
    assert "--wait-timeout 2m" in workflow
    assert "sleep 10" not in workflow
    assert "sleep 60" not in workflow


def test_smoke_waits_for_both_deploys_and_checks_installer_route() -> None:
    workflow = text()
    smoke = workflow.split("\n  smoke:\n", 1)[1].split("\n  summary:\n", 1)[0]

    assert "needs: [preflight, deploy-api, deploy-frontend]" in smoke
    assert "needs.deploy-api.result == 'success'" in smoke
    assert "needs.deploy-frontend.result == 'success'" in smoke
    assert "/hub-lowcode/copilot-memory/instalar" in smoke
    assert "validate_public_runtime.py" in smoke
    assert "validate_publication_sync.py" in smoke


def test_summary_fails_closed_when_any_required_stage_fails() -> None:
    workflow = text()
    summary = workflow.split("\n  summary:\n", 1)[1]

    assert 'if [ "$API_RESULT" != "success" ]' in summary
    assert '[ "$FRONTEND_RESULT" != "success" ]' in summary
    assert '[ "$SMOKE_RESULT" != "success" ]' in summary
    assert "exit 1" in summary
