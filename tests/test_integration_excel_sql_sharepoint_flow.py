from backend.app.services.integration_excel_sql_sharepoint_flow import (
    EXCEL_API,
    SHAREPOINT_API,
    SQL_API,
    gerar_definicao,
    validar_definicao_real,
)


def payload():
    return {
        "target_environment": "dev",
        "excel_source": "https://contoso.sharepoint.com/sites/ReqSysDev",
        "excel_drive": "drive-id",
        "excel_file": "file-id",
        "excel_table": "tbEntrada",
        "sql_procedure": "integration.usp_ConsultarPorIdentificadores",
        "sharepoint_site": "https://contoso.sharepoint.com/sites/ReqSysDev",
        "sharepoint_list": "ResultadoConsulta",
        "correlation_id": "corr-e2e-test",
    }


def walk(actions):
    for action in actions.values():
        yield action
        nested = action.get("actions")
        if isinstance(nested, dict):
            yield from walk(nested)
        else_actions = action.get("else", {}).get("actions")
        if isinstance(else_actions, dict):
            yield from walk(else_actions)


def test_gera_fluxo_real_com_operacoes_esperadas():
    definition = gerar_definicao(payload())
    assert validar_definicao_real(definition) == []
    assert definition["parameters"]["CORRELATION_ID"]["defaultValue"] == "corr-e2e-test"

    operations = {
        (
            action["inputs"]["host"]["apiId"],
            action["inputs"]["host"]["operationId"],
        )
        for action in walk(definition["actions"])
        if action.get("type") == "OpenApiConnection"
    }
    assert (EXCEL_API, "GetItems") in operations
    assert (SQL_API, "ExecuteProcedure_V2") in operations
    assert (SHAREPOINT_API, "GetItems") in operations
    assert (SHAREPOINT_API, "PostItem") in operations
    assert (SHAREPOINT_API, "PatchItem") in operations


def test_rejeita_antes_do_sql_e_propaga_correlation_id():
    definition = gerar_definicao(payload())
    raw = repr(definition)
    assert "isInt(" in raw
    assert "Rejeitar_identificador_invalido" in raw
    assert "rejected_before_sql" in raw
    assert "CORRELATION_ID" in raw
    assert "ChaveIntegracao" in raw


def test_sql_v2_usa_parametros_seguros():
    definition = gerar_definicao(payload())
    sql_actions = [
        action
        for action in walk(definition["actions"])
        if action.get("type") == "OpenApiConnection"
        and action["inputs"]["host"]["apiId"] == SQL_API
    ]
    assert len(sql_actions) == 1
    parameters = sql_actions[0]["inputs"]["parameters"]
    assert parameters["server"] == "default"
    assert parameters["database"] == "default"
    assert parameters["procedure"] == "integration.usp_ConsultarPorIdentificadores"
    assert "parameters/IdsJson" in parameters
    assert parameters["parameters/CorrelationId"] == "@parameters('CORRELATION_ID')"


def test_bloqueia_fora_de_dev():
    data = payload()
    data["target_environment"] = "prod"
    try:
        gerar_definicao(data)
    except ValueError as exc:
        assert "restrita a DEV" in str(exc)
    else:
        raise AssertionError("produção deveria ser bloqueada")
