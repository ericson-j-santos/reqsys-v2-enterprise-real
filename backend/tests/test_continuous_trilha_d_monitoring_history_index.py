from app.services.continuous_trilha_d_monitoring_history_index import (
    carregar_continuous_trilha_d_monitoring_history_index,
)


def test_carregar_continuous_trilha_d_monitoring_history_index_expoe_summary():
    index = carregar_continuous_trilha_d_monitoring_history_index()
    assert 'summary' in index
    assert 'history' in index
    assert 'continuous_trilha_d_monitoring_history_enabled' in index['summary']
