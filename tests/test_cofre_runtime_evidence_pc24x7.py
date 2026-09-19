from pathlib import Path

import yaml

WORKFLOW = Path(".github/workflows/cofre-runtime-evidence-gate.yml")
REMOTE_CONTROL = Path("scripts/cofre_remote_runtime_control.py")
PC24X7_OVERLAY = Path("docker-compose.pc24x7-cofre.yml")


def test_workflow_uses_pc24x7_dev_without_fly_or_self_hosted_runner():
    raw = WORKFLOW.read_text(encoding="utf-8")
    lowered = raw.lower()

    assert "PC24X7_DEV_BASE_URL" in raw
    assert "pc24x7" in lowered
    assert "flyctl" not in lowered
    assert "reqsys-api-dev.fly.dev" not in lowered
    assert "FLY_API_TOKEN" not in raw
    assert "self-hosted" not in raw
    assert "fromJSON(needs.validate-inputs.outputs.runner_labels)" not in raw
    assert "runs-on: ubuntu-latest" in raw
    assert "runner.temp" not in raw


def test_workflow_is_dev_only_and_uses_authenticated_remote_restart():
    raw = WORKFLOW.read_text(encoding="utf-8")
    document = yaml.safe_load(raw)
    jobs = document["jobs"]

    assert "validate-inputs" in jobs
    assert "runtime-evidence" in jobs
    assert "Somente DEV é permitido" in raw
    assert "cofre_remote_runtime_control.py inspect" in raw
    assert "cofre_remote_runtime_control.py restart" in raw
    assert "cofre_remote_runtime_control.py verify" in raw
    assert "pc24x7_cofre_runtime_control.py restart" not in raw


def test_workflow_proves_same_sha_restart_before_persistence_check():
    raw = WORKFLOW.read_text(encoding="utf-8")
    preflight = raw.index("Validar runtime remoto PC24x7 e SHA antes da mutação")
    before = raw.index("Validar ciclo antes do restart")
    restart = raw.index("Solicitar restart autenticado somente da API DEV")
    verify = raw.index("Comprovar novo boot no mesmo SHA")
    after = raw.index("Validar persistência e cleanup")

    assert preflight < before < restart < verify < after
    assert "--expected-sha" in raw
    assert "runtime-restart-verified.json" in raw
    assert "boot_id_changed" in raw
    assert "cofre_runtime_evidence.py" in raw


def test_pc24x7_overlay_explicitly_enables_dev_only_self_restart():
    raw = PC24X7_OVERLAY.read_text(encoding="utf-8")

    assert 'REQSYS_RUNTIME_ENVIRONMENT: "dev"' in raw
    assert 'COFRE_RUNTIME_SELF_RESTART_ENABLED: "1"' in raw
    assert "docker.sock" not in raw.lower()


def test_remote_control_client_never_accepts_non_dev_or_sha_drift():
    raw = REMOTE_CONTROL.read_text(encoding="utf-8")

    assert 'data.get("environment") != "dev"' in raw
    assert 'data.get("runtime_sha") != expected_sha' in raw
    assert '"boot_id_changed": True' in raw
    assert '"production_touched": False' in raw
    assert "Docker" not in raw or "Docker/host credentials" in raw
