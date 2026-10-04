from app.core.config import Settings


def test_catalogo_remoto_permanece_sem_destino_executavel() -> None:
    config = Settings(_env_file=None)

    for ambiente in ('homologacao', 'producao'):
        assert config.ambientes_urls[ambiente]['frontend'] == ''
        assert config.ambientes_urls[ambiente]['api'] == ''


def test_catalogo_ignora_overrides_do_provedor_retirado() -> None:
    config = Settings(
        _env_file=None,
        app_environment='production',
        app_public_url='https://reqsys-app.fly.dev',
        api_public_url='https://reqsys-api.fly.dev/docs',
    )

    assert config.ambiente_atual_info['frontend'] == ''
    assert config.ambiente_atual_info['api'] == ''
    assert config.azure_expected_redirect_uri == ''


def test_catalogo_aceita_override_explicito_fora_do_provedor_retirado() -> None:
    config = Settings(
        _env_file=None,
        app_environment='production',
        app_public_url='https://app.example.test',
        api_public_url='https://api.example.test/docs',
    )

    assert config.ambiente_atual_info['frontend'] == 'https://app.example.test'
    assert config.ambiente_atual_info['api'] == 'https://api.example.test/docs'


def test_catalogo_ignora_override_que_nao_e_url_http_absoluta() -> None:
    config = Settings(
        _env_file=None,
        app_environment='production',
        app_public_url='runtime-interno',
        api_public_url='same-origin:/api',
    )

    assert config.ambiente_atual_info['frontend'] == ''
    assert config.ambiente_atual_info['api'] == ''
