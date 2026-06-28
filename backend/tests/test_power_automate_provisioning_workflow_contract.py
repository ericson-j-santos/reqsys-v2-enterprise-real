from pathlib import Path


def _repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        if (parent / '.git').exists() or (parent / '.github').exists():
            return parent
    raise AssertionError('Nao foi possivel resolver a raiz do repositorio')


def test_power_automate_provisioning_workflow_has_registry_callbacks():
    workflow_path = _repo_root() / '.github' / 'workflows' / 'power-automate-flow-provisioning-p0.yml'
    workflow = workflow_path.read_text(encoding='utf-8')

    assert 'REQSYS_API_BASE_URL' in workflow
    assert 'REQSYS_PROVISIONING_STATUS_TOKEN' in workflow
    assert 'Notify registry running' in workflow
    assert 'Notify registry succeeded' in workflow
    assert 'Notify registry failed' in workflow
    assert "status = 'running'" in workflow
    assert "status = 'succeeded'" in workflow
    assert "status = 'failed'" in workflow
    assert '/v1/hub-lowcode/power-automate/flows/provisioning-registry/' in workflow
    assert 'workflow_run_url' in workflow
    assert 'artifact_url' in workflow
