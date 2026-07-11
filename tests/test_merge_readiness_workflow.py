from pathlib import Path

WORKFLOW = Path('.github/workflows/merge-readiness.yml')


def read_workflow() -> str:
    return WORKFLOW.read_text(encoding='utf-8')


def test_merge_readiness_has_router_job_always_active():
    text = read_workflow()

    assert 'name: Readiness Router' in text
    assert 'needs: readiness-router' in text
    assert "if: needs.readiness-router.outputs.run_gate == 'true'" not in text.split('name: Merge readiness', 1)[1].split('steps:', 1)[0]
    assert 'Registrar execução não aplicável' in text
    assert 'draft_pull_request' in text


def test_merge_readiness_avoids_cancel_in_progress_race():
    text = read_workflow()

    assert 'cancel-in-progress: false' in text


def test_merge_readiness_supports_push_on_main_for_history():
    text = read_workflow()

    assert 'push:' in text
    assert 'branches: [main]' in text
    assert 'scripts/build_merge_readiness_history.py' in text


def test_merge_readiness_validates_environment_promotion_contract():
    text = read_workflow()

    assert 'Validar contrato de promotion readiness' in text
    assert 'tests/test_environment_promotion_readiness.py' in text
    assert 'build_environment_promotion_readiness.py' in text
    assert 'validate_environment_promotion_readiness.py' in text
    assert 'artifacts/environment-promotion-readiness/environment-promotion-readiness.json' in text


def test_merge_readiness_listens_to_draft_transition():
    text = read_workflow()

    assert 'converted_to_draft' in text
