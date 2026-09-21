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
    assert "github.event.comment.body == '/reqsys run fly-dev-fast-deploy'" in content
    assert "github.event.comment.body == '/reqsys run runtime-e2e-dev'" in content
    assert "github.event.comment.body == '/reqsys run pending-agent-pr-permission-watch'" in content
    assert "github.event.comment.body == '/reqsys run bacen-57-simulation-assessment'" in content
    assert "github.event.comment.body == '/reqsys run cofre-runtime-evidence-dev'" in content
    assert "github.event.comment.body == '/reqsys run desktop-rdc-recovery'" in content
    assert "github.event.comment.body == '/reqsys run noteri-control-plane-probe'" in content
    assert "github.event.comment.body == '/reqsys run noteri-headless-control-plane-activation'" in content
    assert "github.event.comment.body == '/reqsys run fabric-oidc-readonly-probe'" in content
    assert "github.event.comment.body == '/reqsys run codex-ollama-e2e-dev'" in content
    assert "github.event.comment.body == '/reqsys run pc24x7-teams-token-bootstrap-dev'" in content
    assert "github.event.comment.body == '/reqsys run pc24x7-teams-e2e-dev'" in content


def test_gateway_usa_allowlist_estatica_sem_workflow_arbitrario() -> None:
    content = _workflow()

    assert "target='bootstrap-wsjf-m365-dev.yml'" in content
    assert "target='fly-dev-fast-deploy.yml'" in content
    assert "target='runtime-e2e-continuous.yml'" in content
    assert "target='pending-development-agent-pr-permission-watch.yml'" in content
    assert "target='bacen-57-simulation-assessment.yml'" in content
    assert "target='cofre-runtime-evidence-gate.yml'" in content
    assert "target='desktop-rdc-recovery.yml'" in content
    assert "target='noteri-control-plane-probe.yml'" in content
    assert "target='noteri-headless-control-plane-activation.yml'" in content
    assert "target='fabric-oidc-readonly-probe.yml'" in content
    assert "target='codex-ollama-e2e-dev.yml'" in content
    assert "target='pc24x7-teams-token-bootstrap.yml'" in content
    assert "target='pc24x7-teams-ephemeral-e2e.yml'" in content
    assert (
        "bootstrap-wsjf-m365-dev.yml|fly-dev-fast-deploy.yml|runtime-e2e-continuous.yml|"
        "pending-development-agent-pr-permission-watch.yml|"
        "bacen-57-simulation-assessment.yml|"
        "cofre-runtime-evidence-gate.yml|"
        "desktop-rdc-recovery.yml|"
        "noteri-control-plane-probe.yml|"
        "noteri-headless-control-plane-activation.yml|"
        "figma-github-e2e-dev.yml|"
        "fabric-oidc-readonly-probe.yml|"
        "codex-ollama-e2e-dev.yml|"
        "pc24x7-teams-token-bootstrap.yml|"
        "pc24x7-teams-ephemeral-e2e.yml"
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
    assert "|desktop-rdc-recovery.yml|noteri-control-plane-probe.yml|noteri-headless-control-plane-activation.yml|figma-github-e2e-dev.yml|fabric-oidc-readonly-probe.yml|codex-ollama-e2e-dev.yml|pc24x7-teams-token-bootstrap.yml|pc24x7-teams-ephemeral-e2e.yml)" in content
    assert "desktop-rdc-recovery-dev" not in content
    assert "-f host=" not in content
    assert "-f task=" not in content


def test_gateway_fly_dev_fast_deploy_fixa_dev_e_input_exato() -> None:
    content = _workflow()

    assert "'/reqsys run fly-dev-fast-deploy')" in content
    assert "target='fly-dev-fast-deploy.yml'" in content
    assert '-f deploy=true' in content
    assert "'production_touched': False" in content
    assert 'deploy=false' not in content


def test_gateway_desktop_rdc_falha_fechado_sem_runner_e_preserva_evidencia() -> None:
    content = _workflow()

    assert "Validate self-hosted runner pickup" in content
    assert 'gh run view "$TARGET_RUN_ID"' in content
    assert "runner_pickup_status" in content
    assert "runner_pickup_error" in content
    assert "SELF_HOSTED_RUNNER_UNAVAILABLE" in content
    assert "steps.pickup.outputs.error == 'SELF_HOSTED_RUNNER_UNAVAILABLE'" in content
    assert "pending|queued|requested|waiting" in content


def test_gateway_vincula_evidencia_ao_run_exato_retornado_pelo_dispatch() -> None:
    content = _workflow()

    assert "id: dispatch" in content
    assert 'run_url="$(gh workflow run "$TARGET_WORKFLOW"' in content
    assert 'run_id="${run_url##*/}"' in content
    assert "TARGET_RUN_ID: ${{ steps.dispatch.outputs.run_id }}" in content
    assert "TARGET_RUN_URL: ${{ steps.dispatch.outputs.run_url }}" in content
    assert 'gh run view "$TARGET_RUN_ID"' in content
    assert "dispatched_run_id_mismatch" in content
    assert "dispatched_run_url_mismatch" in content
    assert "dispatched_run_sha_mismatch" in content
    assert "dispatched_run_event_mismatch" in content
    assert "gh run list" not in content


def test_gateway_desktop_rdc_considera_pending_como_runner_nao_adquirido() -> None:
    content = _workflow()

    assert "status='pending'" in content
    assert "pending|queued|requested|waiting" in content
    assert "SELF_HOSTED_RUNNER_UNAVAILABLE" in content
    assert "steps.pickup.outputs.error == 'SELF_HOSTED_RUNNER_UNAVAILABLE'" in content


def test_gateway_noteri_fallback_is_exact_inputless_and_fail_closed() -> None:
    content = _workflow()

    assert "'/reqsys run noteri-control-plane-probe')" in content
    assert "target='noteri-control-plane-probe.yml'" in content
    assert "steps.route.outputs.target == 'noteri-control-plane-probe.yml'" in content
    assert "SELF_HOSTED_RUNNER_UNAVAILABLE" in content
    assert "-f host=" not in content
    assert "-f command=" not in content


def test_gateway_cancela_run_self_hosted_sem_pickup_e_registra_cleanup() -> None:
    content = _workflow()

    assert "Cancel self-hosted run without pickup" in content
    assert 'gh run cancel "$TARGET_RUN_ID"' in content
    assert "RUN_CANCEL_REQUEST_FAILED" in content
    assert "RUN_CANCEL_NOT_CONFIRMED" in content
    assert "target_cleanup_status" in content
    assert "target_cleanup_error" in content
    assert "steps.cleanup.outputs.status" in content
    assert "steps.cleanup.outputs.error" in content
    assert "[.status, (.conclusion // \"\")] | @tsv" in content
    assert "IFS=$'\\t' read -r status conclusion" in content
    assert "[ \"$status\" = 'completed' ]" in content
    assert "[ \"$conclusion\" = 'cancelled' ]" in content



def test_gateway_noteri_headless_activation_is_exact_inputless_and_fail_closed() -> None:
    content = _workflow()

    assert "'/reqsys run noteri-headless-control-plane-activation')" in content
    assert "target='noteri-headless-control-plane-activation.yml'" in content
    assert "steps.route.outputs.target == 'noteri-headless-control-plane-activation.yml'" in content
    assert "SELF_HOSTED_RUNNER_UNAVAILABLE" in content
    assert "-f host=" not in content
    assert "-f command=" not in content


def test_gateway_teams_ai_dev_dispatches_sao_exatos_e_nonprod() -> None:
    content = _workflow()

    assert "'/reqsys run pc24x7-teams-token-bootstrap-dev')" in content
    assert "target='pc24x7-teams-token-bootstrap.yml'" in content
    assert "'/reqsys run pc24x7-teams-e2e-dev')" in content
    assert "target='pc24x7-teams-ephemeral-e2e.yml'" in content
    assert "'production_touched': False" in content
    assert "'secrets_read': False" in content
    assert "-f environment=prod" not in content
    assert "-f environment=stg" not in content
    assert "-f workflow=" not in content
    assert "eval " not in content
