from pathlib import Path

AUTO = Path(".github/workflows/fly-automatic-environment-promotion.yml")
CAPTURE = Path(".github/workflows/fly-environment-evidence-capture.yml")
STAGE = Path(".github/workflows/fly-environment-promotion-stage.yml")


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_automatic_pipeline_is_post_merge_and_hourly() -> None:
    workflow = text(AUTO)
    assert 'workflows: ["Post-merge Main Runtime Validator"]' in workflow
    assert 'cron: "23 * * * *"' in workflow
    assert "WORKFLOW_CONCLUSION" in workflow
    assert "source_workflow_not_eligible" in workflow
    assert "stale_sha_superseded_by_main" in workflow


def test_promotion_order_is_strictly_sequential() -> None:
    workflow = text(AUTO)
    assert workflow.index("\n  capture-dev:\n") < workflow.index("\n  promote-dev:\n")
    assert workflow.index("\n  dev-result:\n") < workflow.index("\n  capture-stg:\n")
    assert workflow.index("\n  stg-result:\n") < workflow.index("\n  capture-prod:\n")
    assert "needs.dev-result.result == 'success'" in workflow
    assert "needs.stg-result.result == 'success'" in workflow


def test_production_requires_bacen_and_has_no_bypass() -> None:
    workflow = text(AUTO)
    stage = text(STAGE)
    assert "REQSYS_PRODUCTION_GOVERNANCE_GATE" in workflow
    assert "uses: ./.github/workflows/bacen-production-hard-gate.yml" in workflow
    assert "needs.bacen-production.outputs.production_allowed == 'true'" in workflow
    assert '"production_gate_bypass_allowed": False' in workflow
    assert "REQSYS_PRODUCTION_GOVERNANCE_GATE" in stage
    assert "enforce: true" in stage
    assert "environment == 'prod'" in stage


def test_capture_collects_fly_runtime_publication_and_login() -> None:
    workflow = text(CAPTURE)
    assert "capture_fly_environment_state.py" in workflow
    assert "validate_public_runtime.py" in workflow
    assert "validate_publication_sync.py" in workflow
    assert "validar_login_multi_ambiente.py" in workflow
    assert "evaluate_environment_promotion_capture.py" in workflow
    assert "secrets.FLY_API_TOKEN" in workflow
    assert "retention-days: 90" in workflow


def test_stage_deploys_exact_current_main_sha_and_verifies() -> None:
    workflow = text(STAGE)
    assert 'ref: ${{ inputs.expected_sha }}' in workflow
    assert 'test "$(git rev-parse origin/main)" = "$TARGET_SHA"' in workflow
    assert "--build-arg \"GITHUB_SHA=$TARGET_SHA\"" in workflow
    assert "Deploy frontend exact source" in workflow
    assert "uses: ./.github/workflows/fly-environment-evidence-capture.yml" in workflow
    assert "strict: true" in workflow
