from app.services.continuous_trilha_d_monitoring_index import (
    carregar_continuous_trilha_d_monitoring_index,
    mapear_cards_continuous_monitoring,
    mapear_secao_continuous_monitoring,
)


def test_carregar_continuous_trilha_d_monitoring_index_expoe_alertas():
    index = carregar_continuous_trilha_d_monitoring_index()
    assert index["schema_version"]
    assert "alerts" in index
    assert "monitoring_enabled" in index


def test_mapear_secao_continuous_monitoring_expoe_contrato():
    index = carregar_continuous_trilha_d_monitoring_index()
    section = mapear_secao_continuous_monitoring(index)
    assert section["id"] == "continuous-trilha-d-monitoring"
    assert section["type"] == "continuous_trilha_d_monitoring"
    assert "alerts" in section["items"]


def test_mapear_cards_continuous_monitoring_expoe_drilldown():
    index = carregar_continuous_trilha_d_monitoring_index()
    cards = mapear_cards_continuous_monitoring(index)
    assert cards[0]["id"] == "continuous-trilha-d-monitoring"
    assert cards[0]["spa_drilldown"]["query"]["secao"] == "trilha-d-monitoring"
