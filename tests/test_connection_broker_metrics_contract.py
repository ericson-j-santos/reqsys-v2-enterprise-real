from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_connection_broker_metrics_preservam_rotas_e_formato_prometheus():
    source = read("backend-dotnet/src/ReqSys.Api/Endpoints/ReqSysEndpoints.cs")

    assert '"/api/connectors/metrics"' in source
    assert '"/connectors/metrics"' in source
    assert '"text/plain; version=0.0.4; charset=utf-8"' in source
    assert "reqsys_connection_broker_capabilities_total" in source
    assert "reqsys_connection_broker_capabilities_by_status_total" in source
    assert "reqsys_connection_broker_capabilities_by_criticality_total" in source
    assert "reqsys_connection_broker_human_confirmation_required_total" in source
    assert "reqsys_connection_broker_audit_events_total" in source


def test_connection_broker_metrics_sanitizam_quebras_de_linha_e_nao_expoem_detalhes():
    source = read("backend-dotnet/src/ReqSys.Api/Endpoints/ReqSysEndpoints.cs")

    assert 'Replace("\\r", string.Empty' in source
    assert 'Replace("\\n", "\\\\n"' in source
    assert "item.Detalhes" not in source
    assert "item.AcaoSugerida" not in source
