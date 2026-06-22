import pytest

from app.services.codex_governado import analisar_governado, validar_conteudo_seguro


def test_bloqueia_conteudo_sensivel():
    achados = validar_conteudo_seguro(['minha senha: exemplo'])
    assert achados


def test_analise_mock_gera_payload_reqsys():
    resultado = analisar_governado(
        provider='mock',
        contexto='validar endpoint governado',
        entrada='codigo sem dado sensivel',
        usuario={'sub': 'tester@example.com'},
        correlation_id='codex-test-001',
        publicar_no_reqsys=False,
    )

    assert resultado['bloqueado'] is False
    assert resultado['correlation_id'] == 'codex-test-001'
    assert resultado['provider'] == 'mock'
    assert resultado['reqsys_payload']['origem'] == 'codex-governado'
    assert resultado['reqsys_publicacao']['publicado'] is False


def test_rate_limit_bloqueia_excesso():
    usuario = {'sub': 'rate-limit@example.com'}
    ultimo = None
    for i in range(25):
        ultimo = analisar_governado(
            provider='mock',
            contexto='ctx',
            entrada=f'entrada {i}',
            usuario=usuario,
            correlation_id=f'codex-rate-{i}',
            publicar_no_reqsys=False,
        )
    assert ultimo is not None
    assert ultimo['bloqueado'] is True
    assert ultimo['motivo'] == 'rate_limit'
