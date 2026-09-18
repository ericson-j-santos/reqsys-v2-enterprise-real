from pathlib import Path

import yaml

WORKFLOW = Path(".github/workflows/cofre-runtime-evidence-gate.yml")
RUNTIME_CONTROL = Path("scripts/pc24x7_cofre_runtime_control.py")


def test_workflow_uses_pc24x7_dev_and_has_no_fly_runtime():
    raw = WORKFLOW.read_text(encoding="utf-8")
    lowered = raw.lower()

    assert "PC24X7_DEV_BASE_URL" in raw
    assert "pc24x7" in lowered
    assert "flyctl" not in lowered
    assert "reqsys-api-dev.fly.dev" not in lowered
    assert "FLY_API_TOKEN" not in raw
    assert "runtime_target = \"pc24x7\"" in raw
    assert "production_touched = $false" in raw
    assert "runner.temp" not in raw


def test_workflow_is_dev_only_until_dev_is_green():
    raw = WORKFLOW.read_text(encoding="utf-8")
    document = yaml.safe_load(raw)
    jobs = document["jobs"]

    assert "validate-inputs" in jobs
    assert "runtime-evidence" in jobs
    assert "Somente DEV é permitido" in raw
    assert 'runner_labels=["self-hosted","Windows","X64","pc24x7","reqsys-dev"]' in raw
    assert "fromJSON(needs.validate-inputs.outputs.runner_labels)" in raw


def test_workflow_validates_before_restart_and_cleans_up_after():
    raw = WORKFLOW.read_text(encoding="utf-8")
    preflight = raw.index("Validar runtime PC24x7 e SHA antes da mutação")
    before = raw.index("Validar ciclo antes do restart")
    restart = raw.index("Reiniciar somente a API DEV no PC24x7")
    after = raw.index("Validar persistência e cleanup")

    assert preflight < before < restart < after
    assert "pc24x7_cofre_runtime_control.py inspect" in raw
    assert "pc24x7_cofre_runtime_control.py restart" in raw
    assert "cofre_runtime_evidence.py --phase before-restart" in raw
    assert "cofre_runtime_evidence.py --phase after-restart" in raw


def test_runtime_control_is_fail_closed_to_exact_dev_container():
    raw = RUNTIME_CONTROL.read_text(encoding="utf-8")

    assert 'CONTAINER = "wt-pc24x7-piloto-api-1"' in raw
    assert 'PROJECT = "wt-pc24x7-piloto"' in raw
    assert 'SERVICE = "api"' in raw
    assert "runtime_sha_mismatch" in raw
    assert "cofre_secret_mount_missing_or_writable" in raw
    assert "cofre_data_volume_missing" in raw
    assert '["restart", CONTAINER]' in raw


