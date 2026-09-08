from pathlib import Path


SCRIPT = Path('scripts/bootstrap_teams_bot_dev_identity.py')


def _text() -> str:
    return SCRIPT.read_text(encoding='utf-8')


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
    assert '"keyvault",\n            "secret",\n            "set"' in text
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


def test_reexecucao_reutiliza_identidade_somente_se_secret_corresponder() -> None:
    text = _text()
    assert 'Há {len(apps)} App Registrations' in text
    assert 'tagged_app_id.lower() != app_id.lower()' in text
    assert 'O segredo {args.secret_name} já existe' in text


def test_script_nao_grava_env_ou_secret_em_arquivo_local() -> None:
    text = _text()
    assert '.env' not in text
    assert 'write_text(client_secret' not in text
    assert 'write_bytes(client_secret' not in text
