from scripts.integration_excel_sql_sharepoint_e2e import (
    build_e2e_workbook,
    choose_candidate,
    matching_items,
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
