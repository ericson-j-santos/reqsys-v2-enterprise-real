from scripts.integration_excel_sql_sharepoint_e2e import (
    build_e2e_workbook,
    choose_candidate,
    matching_items,
    select_positive_identifier,
    workbook_candidates,
)


def test_workbook_e2e_contem_positivo_e_negativo():
    content = build_e2e_workbook("12345", "INVALIDO-X")
    assert workbook_candidates(content) == ["12345"]


def test_matching_items_usa_chave_integracao_exata():
    items = [
        {"id": "1", "fields": {"ChaveIntegracao": "123"}},
        {"id": "2", "fields": {"ChaveIntegracao": "1234"}},
    ]
    assert [item["id"] for item in matching_items(items, "123")] == ["1"]


def test_choose_candidate_ignora_residuo(monkeypatch):
    calls = []

    def fake_probe(_dsn, _procedure, identifier):
        calls.append(identifier)
        return [{"Identificador": identifier}]

    monkeypatch.setattr(
        "scripts.integration_excel_sql_sharepoint_e2e.execute_sql_probe",
        fake_probe,
    )
    selected, row = choose_candidate(
        ["111", "222"],
        sql_dsn="dsn",
        procedure="integration.usp_ConsultarPorIdentificadores",
        existing_items=[{"id": "old", "fields": {"ChaveIntegracao": "111"}}],
    )
    assert selected == "222"
    assert row["Identificador"] == "222"
    assert calls == ["222"]


def test_gateway_mode_uses_configured_fixture_without_direct_sql_probe(monkeypatch):
    monkeypatch.setattr(
        "scripts.integration_excel_sql_sharepoint_e2e.execute_sql_probe",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("direct SQL probe must not run")),
    )
    selected, row = select_positive_identifier(
        validation_mode="power_platform_gateway",
        candidates=[],
        fixture_id="990000000000001",
        sql_dsn="",
        procedure="integration.usp_ConsultarPorIdentificadores",
        existing_items=[],
    )
    assert selected == "990000000000001"
    assert row is None


def test_gateway_mode_rejects_invalid_fixture_and_sharepoint_residue():
    import pytest
    with pytest.raises(RuntimeError, match="sql_fixture_id_invalido"):
        select_positive_identifier(
            validation_mode="power_platform_gateway", candidates=[], fixture_id="INVALID",
            sql_dsn="", procedure="integration.usp_ConsultarPorIdentificadores", existing_items=[]
        )
    with pytest.raises(RuntimeError, match="baseline_sharepoint_residual_detectado"):
        select_positive_identifier(
            validation_mode="power_platform_gateway", candidates=[], fixture_id="990000000000001",
            sql_dsn="", procedure="integration.usp_ConsultarPorIdentificadores",
            existing_items=[{"id": "1", "fields": {"ChaveIntegracao": "990000000000001"}}]
        )
