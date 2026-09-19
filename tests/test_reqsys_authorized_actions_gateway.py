from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/reqsys-authorized-actions-gateway.yml"


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_gateway_restringe_issue_ator_e_comandos_exatos() -> None:
    content = _workflow()

    assert "github.event.issue.number == 1705" in content
    assert "github.event.comment.user.login == 'ericson-j-santos'" in content
    assert "github.event.comment.body == '/reqsys run bootstrap-wsjf-m365-dev'" in content
    assert "github.event.comment.body == '/reqsys run runtime-e2e-dev'" in content
    assert "github.event.comment.body == '/reqsys run pending-agent-pr-permission-watch'" in content
    assert "github.event.comment.body == '/reqsys run bacen-57-simulation-assessment'" in content
    assert "github.event.comment.body == '/reqsys run cofre-runtime-evidence-dev'" in content
    assert "github.event.comment.body == '/reqsys run desktop-rdc-recovery'" in content


def test_gateway_usa_allowlist_estatica_sem_workflow_arbitrario() -> None:
    content = _workflow()

    assert "target='bootstrap-wsjf-m365-dev.yml'" in content
    assert "target='runtime-e2e-continuous.yml'" in content
    assert "target='pending-development-agent-pr-permission-watch.yml'" in content
    assert "target='bacen-57-simulation-assessment.yml'" in content
    assert "target='cofre-runtime-evidence-gate.yml'" in content
    assert "target='desktop-rdc-recovery.yml'" in content
    assert (
        "bootstrap-wsjf-m365-dev.yml|runtime-e2e-continuous.yml|"
        "pending-development-agent-pr-permission-watch.yml|"
        "bacen-57-simulation-assessment.yml|"
        "cofre-runtime-evidence-gate.yml|"
        "desktop-rdc-recovery.yml"
    ) in content
    assert 'gh workflow run "$TARGET_WORKFLOW"' in content
    assert "eval " not in content


def test_gateway_bacen_57_permanece_somente_simulacao_nonprod() -> None:
    content = _workflow()

    assert "'/reqsys run bacen-57-simulation-assessment')" in content
    assert "target='bacen-57-simulation-assessment.yml'" in content
    assert "'production_touched': False" in content
    assert "'secrets_read': False" in content


def test_gateway_fixa_main_e_permissoes_minimas() -> None:
    content = _workflow()

    permissions = content.split("permissions:\n", maxsplit=1)[1].split("\n\n", maxsplit=1)[0]
    assert "actions: write" in permissions
    assert "contents: read" in permissions
    assert "contents: write" not in permissions
    assert "id-token: write" not in permissions
    assert "--ref main" in content
    assert "target_ref': 'main'" in content


def test_gateway_publica_evidencia_sanitizada() -> None:
    content = _workflow()

    assert "authorized-action-dispatch.json" in content
    assert "'secrets_read': False" in content
    assert "'production_touched': False" in content
    assert "target_run_url" in content
    assert "target_sha" in content


def test_gateway_cofre_fixa_dev_e_timeout_sem_producao() -> None:
    content = _workflow()

    assert "'/reqsys run cofre-runtime-evidence-dev')" in content
    assert "target='cofre-runtime-evidence-gate.yml'" in content
    assert '-f environment=dev' in content
    assert '-f timeout_seconds=20' in content
    assert 'environment=stg' not in content
    assert 'environment=prod' not in content


def test_gateway_desktop_rdc_recovery_is_exact_and_inputless() -> None:
    content = _workflow()

    assert "'/reqsys run desktop-rdc-recovery')" in content
    assert "target='desktop-rdc-recovery.yml'" in content
    assert "desktop-rdc-recovery.yml)" in content
    assert "|desktop-rdc-recovery.yml)" in content
    assert "desktop-rdc-recovery-dev" not in content
    assert "-f host=" not in content
    assert "-f task=" not in content


def test_gateway_desktop_rdc_falha_fechado_sem_runner_e_preserva_evidencia() -> None:
    content = _workflow()

    assert "Validate desktop recovery runner pickup" in content
    assert 'gh run view "$TARGET_RUN_ID"' in content
    assert "runner_pickup_status" in content
    assert "runner_pickup_error" in content
    assert "SELF_HOSTED_RUNNER_UNAVAILABLE" in content
    assert "steps.pickup.outputs.status == 'queued'" in content
