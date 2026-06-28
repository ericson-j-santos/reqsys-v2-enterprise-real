from app.services.external_sources_registry import resumo_fontes_externas, validar_registry_producao


def test_resumo_fontes_externas_conta_pendentes():
    resumo = resumo_fontes_externas()
    assert resumo['total'] >= 1
    assert resumo['pendentes_auditoria'] >= 1


def test_validar_registry_producao_permite_mock_false(monkeypatch):
    from app.core import config as config_module

    monkeypatch.setattr(config_module.settings, 'app_environment', 'production')
    validar_registry_producao()
