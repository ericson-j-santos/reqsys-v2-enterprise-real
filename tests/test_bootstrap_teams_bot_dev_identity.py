import importlib.util
import json
import subprocess
from pathlib import Path

import pytest


SCRIPT = Path('scripts/bootstrap_teams_bot_dev_identity.py')
SPEC = importlib.util.spec_from_file_location('bootstrap_teams_bot_dev_identity', SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

TENANT = '6d09c88c-0617-490c-8329-305e577684bc'
SECRET_VALUE = 'valor-do-segredo-que-nunca-pode-vazar'


def _text() -> str:
    return SCRIPT.read_text(encoding='utf-8')


# ---------------------------------------------------------------------------
# Contrato textual: invariantes de segurança que não dependem de execução.
# ---------------------------------------------------------------------------


def test_bootstrap_exige_confirmacao_literal() -> None:
    text = _text()
    assert 'CRIAR-IDENTIDADE-TEAMS-BOT-DEV' in text
    assert 'if args.confirm != CONFIRMATION' in text


def test_bootstrap_cria_identidade_dedicada_single_tenant() -> None:
    text = _text()
    assert 'ReqSys Teams Bot DEV' in text
    assert '"ad",\n            "app",\n            "create"' in text
    assert 'AzureADMyOrg' in text
    assert '"ad", "sp", "create"' in text


def test_bootstrap_grava_secret_diretamente_no_keyvault() -> None:
    text = _text()
    assert 'kv-reqsys-ccp' in text
    assert 'reqsys-teams-bot-dev-secret' in text
    assert '"keyvault",' in text and '"secret",' in text and '"set",' in text
    assert 'f"app-id={app_id}"' in text
    assert 'environment=dev' in text


def test_valor_secreto_nunca_e_publicado_na_evidencia() -> None:
    text = _text()
    assert '"secret_value_exposed": False' in text
    assert 'print(client_secret' not in text
    assert 'print(password' not in text
    assert 'output.write_text(json.dumps(evidence' in text
    assert '"secret": client_secret' not in text
    assert '"password": client_secret' not in text


def test_operacao_sensivel_suprime_detalhes_em_falha() -> None:
    text = _text()
    assert 'if sensitive:' in text
    assert 'detalhes foram suprimidos para não expor credenciais' in text
    assert 'sensitive=True' in text


def test_script_nao_grava_env_ou_secret_em_arquivo_local() -> None:
    text = _text()
    assert '.env' not in text
    assert 'write_text(client_secret' not in text
    assert 'write_bytes(client_secret' not in text


# ---------------------------------------------------------------------------
# Contrato executável: o Azure CLI é simulado; a lógica real do script roda.
# ---------------------------------------------------------------------------


class FakeAz:
    """Substitui o Azure CLI preservando a semântica de retorno do 'az'."""

    def __init__(
        self,
        *,
        apps: list[dict] | None = None,
        service_principal_exists: bool = False,
        secret: dict | None = None,
        vault_reachable: bool = True,
        credential_reset_rc: int = 0,
        keyvault_set_rc: int = 0,
        tenant_id: str = TENANT,
    ) -> None:
        self.apps = list(apps or [])
        self.service_principal_exists = service_principal_exists
        self.secret = secret
        self.vault_reachable = vault_reachable
        self.credential_reset_rc = credential_reset_rc
        self.keyvault_set_rc = keyvault_set_rc
        self.tenant_id = tenant_id
        self.credential_keys: set[str] = set()
        self.stored_secret_args: list[str] | None = None
        self.calls: list[list[str]] = []

    def command(self, args: list[str]) -> list[str]:
        return [item for item in args[1:] if not item.startswith('-')]

    def executed(self, *prefix: str) -> list[list[str]]:
        return [call for call in self.calls if self.command(call)[: len(prefix)] == list(prefix)]

    def __call__(self, args, **_: object) -> subprocess.CompletedProcess:
        call = list(args)
        self.calls.append(call)
        cmd = self.command(call)

        def done(rc: int = 0, stdout: str = '') -> subprocess.CompletedProcess:
            return subprocess.CompletedProcess(call, rc, stdout, '' if rc == 0 else 'falha simulada')

        if cmd[:2] == ['account', 'show']:
            return done(0, json.dumps({'tenantId': self.tenant_id, 'id': 'sub'}))
        if cmd[:3] == ['keyvault', 'secret', 'list']:
            return done(0 if self.vault_reachable else 1)
        if cmd[:3] == ['ad', 'app', 'list']:
            return done(0, json.dumps(self.apps))
        if cmd[:3] == ['ad', 'sp', 'show']:
            return done(0 if self.service_principal_exists else 1)
        if cmd[:3] == ['ad', 'sp', 'create']:
            self.service_principal_exists = True
            return done()
        if cmd[:3] == ['keyvault', 'secret', 'show']:
            if self.secret is None:
                return done(1)
            return done(0, json.dumps(self.secret))
        if cmd[:4] == ['ad', 'app', 'credential', 'list']:
            return done(0, json.dumps(sorted(self.credential_keys)))
        if cmd[:4] == ['ad', 'app', 'credential', 'reset']:
            if self.credential_reset_rc != 0:
                return done(self.credential_reset_rc)
            self.credential_keys.add('key-nova')
            return done(0, SECRET_VALUE + '\n')
        if cmd[:4] == ['ad', 'app', 'credential', 'delete']:
            key_id = call[call.index('--key-id') + 1]
            self.credential_keys.discard(key_id)
            return done()
        if cmd[:3] == ['ad', 'app', 'create']:
            app = {'id': 'objeto-novo', 'appId': 'app-novo', 'displayName': MODULE.DEFAULT_APP_NAME}
            self.apps.append(dict(app, signInAudience='AzureADMyOrg'))
            return done(0, json.dumps(app))
        if cmd[:3] == ['ad', 'app', 'delete']:
            self.apps = [app for app in self.apps if app.get('id') != call[call.index('--id') + 1]]
            return done()
        if cmd[:3] == ['keyvault', 'secret', 'set']:
            if self.keyvault_set_rc != 0:
                return done(self.keyvault_set_rc)
            self.stored_secret_args = call
            return done()
        raise AssertionError(f'comando não previsto no teste: {cmd}')


@pytest.fixture
def az(monkeypatch: pytest.MonkeyPatch):
    def _install(fake: FakeAz) -> FakeAz:
        monkeypatch.setattr(MODULE, '_cli', lambda: '/usr/bin/az')
        monkeypatch.setattr(MODULE.subprocess, 'run', fake)
        return fake

    return _install


def _args(**overrides):
    argv = ['--confirm', MODULE.CONFIRMATION, '--tenant-id', TENANT]
    for key, value in overrides.items():
        if value is True:
            argv.append(f'--{key.replace("_", "-")}')
        else:
            argv.extend([f'--{key.replace("_", "-")}', str(value)])
    return MODULE.parse_args(argv)


APP_EXISTENTE = {'id': 'objeto-existente', 'appId': 'app-existente', 'displayName': MODULE.DEFAULT_APP_NAME, 'signInAudience': 'AzureADMyOrg'}


def test_azure_cli_ausente_produz_erro_acionavel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MODULE.shutil, 'which', lambda _: None)
    with pytest.raises(MODULE.BootstrapError, match='Azure CLI não encontrado'):
        MODULE._cli()


def test_confirmacao_invalida_nao_toca_no_azure(az) -> None:
    fake = az(FakeAz())
    with pytest.raises(MODULE.BootstrapError, match='Confirmação inválida'):
        MODULE.bootstrap(MODULE.parse_args(['--confirm', 'errado']))
    assert fake.calls == []


def test_tenant_divergente_bloqueia_antes_de_qualquer_mutacao(az) -> None:
    fake = az(FakeAz(tenant_id='outro-tenant'))
    with pytest.raises(MODULE.BootstrapError, match='difere do tenant esperado'):
        MODULE.bootstrap(_args())
    assert fake.executed('ad', 'app', 'create') == []
    assert fake.executed('ad', 'app', 'credential', 'reset') == []


def test_cofre_inacessivel_aborta_antes_de_criar_identidade(az) -> None:
    fake = az(FakeAz(vault_reachable=False))
    with pytest.raises(MODULE.BootstrapError, match=MODULE.VAULT_WRITE_ROLE):
        MODULE.bootstrap(_args())
    assert fake.executed('ad', 'app', 'create') == []
    assert fake.executed('ad', 'app', 'credential', 'reset') == []


def test_dry_run_nao_executa_nenhuma_mutacao(az) -> None:
    fake = az(FakeAz())
    evidence = MODULE.bootstrap(_args(dry_run=True))
    assert evidence['status'] == 'dry_run'
    assert evidence['secret_value_exposed'] is False
    assert any('criar App Registration' in action for action in evidence['planned_actions'])
    for mutation in (('ad', 'app', 'create'), ('ad', 'sp', 'create'), ('ad', 'app', 'credential', 'reset'), ('keyvault', 'secret', 'set')):
        assert fake.executed(*mutation) == []


def test_bootstrap_completo_grava_secret_com_tag_app_id(az) -> None:
    fake = az(FakeAz())
    evidence = MODULE.bootstrap(_args())
    assert evidence['status'] == 'ready'
    assert evidence['created_app'] is True
    assert evidence['created_service_principal'] is True
    assert evidence['secret_created'] is True
    assert evidence['app_id'] == 'app-novo'
    assert fake.stored_secret_args is not None
    assert 'app-id=app-novo' in fake.stored_secret_args
    assert SECRET_VALUE not in json.dumps(evidence, ensure_ascii=False)


def test_falha_ao_gravar_no_keyvault_revoga_credencial_e_remove_app_criada(az) -> None:
    fake = az(FakeAz(keyvault_set_rc=1))
    with pytest.raises(MODULE.BootstrapError) as error:
        MODULE.bootstrap(_args())
    assert SECRET_VALUE not in str(error.value)
    assert MODULE.VAULT_WRITE_ROLE in str(error.value)
    assert fake.credential_keys == set()
    assert fake.executed('ad', 'app', 'credential', 'delete')
    assert fake.executed('ad', 'app', 'delete')


def test_falha_no_keyvault_revoga_credencial_sem_apagar_app_preexistente(az) -> None:
    fake = az(FakeAz(apps=[dict(APP_EXISTENTE)], service_principal_exists=True, keyvault_set_rc=1))
    with pytest.raises(MODULE.BootstrapError):
        MODULE.bootstrap(_args())
    assert fake.credential_keys == set()
    assert fake.executed('ad', 'app', 'credential', 'delete')
    assert fake.executed('ad', 'app', 'delete') == []


def test_app_existente_fora_do_single_tenant_e_recusada(az) -> None:
    fake = az(FakeAz(apps=[dict(APP_EXISTENTE, signInAudience='AzureADMultipleOrgs')]))
    with pytest.raises(MODULE.BootstrapError, match='AzureADMyOrg'):
        MODULE.bootstrap(_args())
    assert fake.executed('ad', 'app', 'credential', 'reset') == []


def test_reexecucao_reutiliza_identidade_quando_secret_corresponde(az) -> None:
    fake = az(
        FakeAz(
            apps=[dict(APP_EXISTENTE)],
            service_principal_exists=True,
            secret={'enabled': True, 'tags': {'app-id': 'app-existente'}},
        )
    )
    evidence = MODULE.bootstrap(_args())
    assert evidence['status'] == 'ready'
    assert evidence['created_app'] is False
    assert evidence['secret_created'] is False
    assert fake.executed('ad', 'app', 'credential', 'reset') == []


def test_secret_existente_com_tag_divergente_e_recusado(az) -> None:
    az(
        FakeAz(
            apps=[dict(APP_EXISTENTE)],
            service_principal_exists=True,
            secret={'enabled': True, 'tags': {'app-id': 'outra-identidade'}},
        )
    )
    with pytest.raises(MODULE.BootstrapError, match='tag app-id não corresponde'):
        MODULE.bootstrap(_args())


def test_secret_desabilitado_e_recusado(az) -> None:
    az(
        FakeAz(
            apps=[dict(APP_EXISTENTE)],
            service_principal_exists=True,
            secret={'enabled': False, 'tags': {'app-id': 'app-existente'}},
        )
    )
    with pytest.raises(MODULE.BootstrapError, match='está desabilitado'):
        MODULE.bootstrap(_args())


def test_identidade_ambigua_bloqueia_o_bootstrap(az) -> None:
    az(FakeAz(apps=[dict(APP_EXISTENTE), dict(APP_EXISTENTE, id='objeto-2', appId='app-2')]))
    with pytest.raises(MODULE.BootstrapError, match='App Registrations'):
        MODULE.bootstrap(_args())


def test_evidencia_persistida_nunca_contem_o_valor_do_segredo(az, tmp_path: Path) -> None:
    az(FakeAz())
    output = tmp_path / 'evidencia.json'
    assert MODULE.main(['--confirm', MODULE.CONFIRMATION, '--tenant-id', TENANT, '--output', str(output)]) == 0
    conteudo = output.read_text(encoding='utf-8')
    assert SECRET_VALUE not in conteudo
    assert json.loads(conteudo)['secret_value_exposed'] is False
