from pathlib import Path


WORKFLOW = Path(".github/workflows/fly-dev-runtime-diagnostic.yml")


def text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_diagnostic_runs_only_after_failed_fast_dev_deploy() -> None:
    workflow = text()

    assert 'workflows: ["Fly DEV Fast Deploy"]' in workflow
    assert "types: [completed]" in workflow
    assert "github.event.workflow_run.conclusion == 'failure'" in workflow
    assert "github.event.workflow_run.head_branch == 'main'" in workflow


def test_diagnostic_is_hardcoded_to_dev_and_read_only() -> None:
    workflow = text()

    assert "environment: dev" in workflow
    assert "FLY_APP: reqsys-api-dev" in workflow
    assert "API_URL: https://reqsys-api-dev.fly.dev" in workflow
    assert "flyctl status --app" in workflow
    assert "flyctl logs --app" in workflow
    assert "flyctl deploy" not in workflow
    assert "flyctl apps restart" not in workflow
    assert "flyctl scale" not in workflow
    assert "flyctl secrets set" not in workflow
    assert "production" not in workflow.lower()


def test_diagnostic_probes_all_public_runtime_endpoints() -> None:
    workflow = text()

    assert "/health /api/runtime/health /api/runtime/readiness /api/runtime/liveness" in workflow
    assert "--connect-timeout 5 --max-time 10" in workflow
    assert "http_code=%{http_code}" in workflow


def test_diagnostic_always_uploads_evidence() -> None:
    workflow = text()

    assert "if: always()" in workflow
    assert "fly-dev-runtime-diagnostic-${{ github.event.workflow_run.id }}" in workflow
    assert "retention-days: 14" in workflow
