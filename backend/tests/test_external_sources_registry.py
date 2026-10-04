from app.services.external_sources_registry import listar_fontes_externas, resumo_fontes_externas, validar_registry_producao


def test_resumo_fontes_externas_conta_autorizadas():
    resumo = resumo_fontes_externas()
    assert resumo['total'] >= 2
    assert resumo['autorizadas_validas'] >= 2
    assert resumo['pendentes_auditoria'] == 0


def test_fontes_externas_possuem_auditoria():
    fontes = listar_fontes_externas()
    assert fontes
    for fonte in fontes:
        assert fonte.autorizado is True
        assert fonte.mock_as_real is False


def test_validar_registry_producao_permite_mock_false(monkeypatch):
    from app.core import config as config_module

    monkeypatch.setattr(config_module.settings, 'app_environment', 'production')
    validar_registry_producao()
