from pathlib import Path

WORKFLOW = Path('.github/workflows/merge-readiness.yml')


def read_workflow() -> str:
    return WORKFLOW.read_text(encoding='utf-8')


def test_merge_readiness_has_router_job_always_active():
    text = read_workflow()

    assert 'name: Readiness Router' in text
    assert 'needs: readiness-router' in text
    assert "needs.readiness-router.outputs.run_gate == 'true'" in text


def test_merge_readiness_avoids_cancel_in_progress_race():
    text = read_workflow()

    assert 'cancel-in-progress: false' in text


def test_merge_readiness_supports_push_on_main_for_history():
    text = read_workflow()

    assert 'push:' in text
    assert 'branches: [main]' in text
    assert 'scripts/build_merge_readiness_history.py' in text
