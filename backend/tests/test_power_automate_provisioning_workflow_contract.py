from tests.shared.repository_paths import resolve_repo_file


def test_power_automate_provisioning_workflow_has_registry_callbacks():
    workflow_path = resolve_repo_file('.github', 'workflows', 'power-automate-flow-provisioning-p0.yml')
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
