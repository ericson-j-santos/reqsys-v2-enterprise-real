import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml


WORKFLOW = Path('.github/workflows/teams-bot-dev-provision.yml')


def _text() -> str:
    return WORKFLOW.read_text(encoding='utf-8')


def _workflow() -> dict:
    return yaml.safe_load(_text())


def test_ativacao_real_nunca_roda_em_pull_request() -> None:
    workflow = _workflow()
    condition = workflow['jobs']['activate-dev']['if']
    assert "github.event_name != 'pull_request'" in condition
    assert "vars.CCP_ENABLED == 'true'" in condition


def test_ativacao_usa_somente_identidade_mutadora_federada_a_main() -> None:
    workflow = _workflow()
    job = workflow['jobs']['activate-dev']
    assert 'environment' not in job
    text = _text()
    assert 'CCP_AZURE_CLIENT_ID: ${{ vars.CCP_AZURE_CLIENT_ID }}' in text
    assert 'client-id: ${{ env.CCP_AZURE_CLIENT_ID }}' in text
    assert 'CCP_AZURE_CLIENT_ID_DEV' not in text
    assert 'resolve-managed-credential' not in text


def test_ci_nao_cria_nem_rotaciona_app_registration() -> None:
    text = _text()
    assert 'az ad app create' not in text
    assert 'az ad app credential reset' not in text
    assert 'az ad sp create' not in text
    assert 'az ad app permission' not in text


def test_identidade_dedicada_vem_de_secret_tag_no_keyvault() -> None:
    text = _text()
    assert 'BOT_SECRET_VAULT_NAME: reqsys-teams-bot-dev-secret' in text
    assert "'.tags[\"app-id\"] // empty'" in text
    assert 'TEAMS_BOT_IDENTITY_BOOTSTRAP_REQUIRED' in text
    assert 'scripts/bootstrap_teams_bot_dev_identity.py' in text


def test_reader_dev_nao_recebe_acesso_ao_secret_do_bot() -> None:
    text = _text()
    assert 'environment: dev' not in text
    assert 'fly-api-dev-deploy' not in text
    assert 'github-actions:fly-dev' not in text


def test_trust_anchor_fly_e_lido_pelo_mutador_e_validado_sem_mutacao() -> None:
    text = _text()
    assert 'FLY_TRUST_ANCHOR_SECRET_NAME: reqsys-fly-control-plane-org-token' in text
    assert '--name "$FLY_TRUST_ANCHOR_SECRET_NAME"' in text
    assert 'FLY_API_TOKEN="$fly_admin_token" flyctl status --app "$FLY_APP" --json' in text
    assert 'FLY_API_TOKEN="$fly_admin_token" flyctl secrets list --app "$FLY_APP"' in text
    assert text.index('flyctl status --app "$FLY_APP" --json') < text.index('az bot create')


def test_bot_e_single_tenant_f0_com_endpoint_exato() -> None:
    text = _text()
    assert '--app-type SingleTenant' in text
    assert '--sku F0' in text
    assert (
        'TARGET_ENDPOINT: https://reqsys-api-dev.fly.dev/v1/teams-gateway/'
        'ai-conversations/bot/messages'
    ) in text
    assert 'az bot msteams create' in text
    assert 'az bot msteams delete' in text


def test_reexecucao_valida_bot_existente_antes_de_reutilizar() -> None:
    text = _text()
    assert 'az bot show --name "$BOT_NAME" --resource-group "$RESOURCE_GROUP"' in text
    assert 'current_app_id=' in text
    assert 'current_endpoint=' in text
    assert 'current_sku=' in text
    assert 'EXISTING_BOT_CONTRACT_MISMATCH' in text


def test_runtime_configura_exatamente_os_tres_segredos_da_1518() -> None:
    text = _text()
    assert 'TEAMS_BOT_APP_ID=$BOT_APP_ID' in text
    assert 'TEAMS_BOT_APP_TENANT_ID=$CCP_AZURE_TENANT_ID' in text
    assert 'TEAMS_BOT_SECRET=$BOT_SECRET' in text
    assert 'FLY_API_TOKEN="$FLY_ADMIN_TOKEN" flyctl secrets set' in text


def test_commit_runtime_impede_rollback_destrutivo_depois_do_fly() -> None:
    text = _text()
    set_secrets = text.index('flyctl secrets set')
    committed = text.index('RUNTIME_COMMITTED=1')
    health = text.index('curl --fail --silent --show-error --retry 8')
    assert set_secrets < committed < health
    assert 'if [ "$RUNTIME_COMMITTED" -eq 0 ]' in text


def test_pacote_teams_usa_app_id_real_e_bot_conversacional() -> None:
    text = _text()
    assert 'APP_ID_FOR_PACKAGE="$BOT_APP_ID" python' in text
    assert "manifest['id'] = app_id" in text
    assert "manifest['bots'][0]['botId'] = app_id" in text
    assert "manifest['bots'][0]['isNotificationOnly'] is False" in text
    assert 'audit/reqsys-teams-gateway-dev-v1.1.0.zip' in text


def test_runtime_valida_saude_dev_depois_dos_segredos() -> None:
    text = _text()
    assert 'HEALTH_URL: https://reqsys-api-dev.fly.dev/health' in text
    assert '--retry 8 --retry-delay 5 --retry-all-errors' in text


def test_escopo_exclusivamente_dev() -> None:
    text = _text()
    assert 'FLY_APP: reqsys-api-dev' in text
    assert 'reqsys-api-stg' not in text
    assert 'APROVO-PROD' not in text


def test_artifact_nao_publica_valores_secretos() -> None:
    text = _text()
    assert 'secret_value_exposed' in text
    assert "'secret_value_exposed': False" in text
    artifact_section = text[text.index('Publicar pacote e evidência da ativação'):]
    assert 'BOT_SECRET' not in artifact_section
    assert 'FLY_ADMIN_TOKEN' not in artifact_section


def _step(job: str, name: str) -> dict:
    for step in _workflow()['jobs'][job]['steps']:
        if step.get('name') == name:
            return step
    raise AssertionError(f'passo não encontrado: {name}')


def test_poll_agendado_retoma_ativacao_apos_bootstrap_humano() -> None:
    workflow = _workflow()
    triggers = workflow[True] if True in workflow else workflow['on']
    assert 'schedule' in triggers
    assert triggers['schedule'] == [{'cron': '23 * * * *'}]
    condition = workflow['jobs']['activate-dev']['if']
    assert 'schedule' not in condition


def test_espera_por_bootstrap_nao_gera_alarme_em_execucao_agendada() -> None:
    script = _step('activate-dev', 'Bloquear até bootstrap humano mínimo')['run']
    assert 'TEAMS_BOT_IDENTITY_BOOTSTRAP_REQUIRED' in script
    assert '"$EVENT_NAME" = "schedule"' in script
    assert 'exit 0' in script
    assert 'exit 20' in script


@pytest.mark.skipif(shutil.which('jq') is None, reason='jq indisponível')
@pytest.mark.parametrize(
    ('event', 'blocker', 'esperado'),
    [
        ('schedule', 'TEAMS_BOT_IDENTITY_BOOTSTRAP_REQUIRED', 0),
        ('schedule', 'EXISTING_BOT_CONTRACT_MISMATCH', 20),
        ('push', 'TEAMS_BOT_IDENTITY_BOOTSTRAP_REQUIRED', 20),
        ('workflow_dispatch', 'TEAMS_BOT_IDENTITY_BOOTSTRAP_REQUIRED', 20),
    ],
)
def test_bloqueio_falha_fechado_exceto_no_poll_de_retomada(
    tmp_path: Path, event: str, blocker: str, esperado: int
) -> None:
    evidence = tmp_path / 'evidencia.json'
    evidence.write_text(json.dumps({'status': 'precondition_failed', 'blocker': blocker}), encoding='utf-8')
    script = _step('activate-dev', 'Bloquear até bootstrap humano mínimo')['run']
    result = subprocess.run(
        ['bash', '-c', script],
        env={'PATH': os.environ['PATH'], 'EVENT_NAME': event, 'EVIDENCE_FILE': str(evidence)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == esperado


def test_runtime_ja_sincronizado_nao_regrava_segredos_no_fly() -> None:
    text = _text()
    assert 'runtime_secrets_present=false' in text
    assert 'echo "runtime_synced=$runtime_synced" >> "$GITHUB_OUTPUT"' in text
    assert 'RUNTIME_ALREADY_SYNCED: ${{ steps.preflight.outputs.runtime_synced }}' in text
    assert '[ "$RUNTIME_ALREADY_SYNCED" != "true" ] || [ "$FORCE_RUNTIME_SYNC" = "true" ]' in text
    assert "'runtime_secret_sync': os.environ['RUNTIME_SECRET_SYNC']" in text


def test_regravacao_do_runtime_pode_ser_forcada_por_dispatch() -> None:
    workflow = _workflow()
    triggers = workflow[True] if True in workflow else workflow['on']
    assert triggers['workflow_dispatch']['inputs']['force_runtime_sync']['default'] is False
    assert 'FORCE_RUNTIME_SYNC: ${{ inputs.force_runtime_sync || false }}' in _text()
