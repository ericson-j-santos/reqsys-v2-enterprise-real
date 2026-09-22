from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from scripts.validar_ambientes_power_platform import (
    RegistroInvalido,
    conferir_destino,
    validar,
)

REGISTRO_REAL = Path("config/power-platform/environments.json")

URL_TEST = "https://orgtest01.crm2.dynamics.com"
URL_PROD = "https://orgprod01.crm2.dynamics.com"
GUID_ENV_TEST = "11111111-1111-4111-8111-111111111111"
GUID_CONN_TEST = "22222222-2222-4222-8222-222222222222"
GUID_ENV_PROD = "33333333-3333-4333-8333-333333333333"
GUID_CONN_PROD = "44444444-4444-4444-8444-444444444444"
REFERENCIA = "reqsys_sharedteams_5f2a1"


def _registro_base() -> dict[str, Any]:
    return json.loads(REGISTRO_REAL.read_text(encoding="utf-8"))


def _com_test_autorizado(registro: dict[str, Any]) -> dict[str, Any]:
    registro = copy.deepcopy(registro)
    registro["ambientes"]["test"].update(
        {
            "status": "CONEXAO_AUTORIZADA",
            "environment_url": URL_TEST,
            "environment_id": GUID_ENV_TEST,
            "connection_id": GUID_CONN_TEST,
            "connection_reference_logical_name": REFERENCIA,
        }
    )
    return registro


def test_registro_versionado_e_valido_e_bloqueia_promocao() -> None:
    relatorio = validar(_registro_base())

    assert relatorio["valido"] is True
    assert relatorio["decision"] == "validated"
    assert relatorio["secret_value_logged"] is False
    assert relatorio["production_touched"] is False
    # Nenhum destino pode ser promovido enquanto a acao humana nao acontecer.
    assert relatorio["ambientes"]["test"]["pronto_para_promocao"] is False
    assert relatorio["ambientes"]["prod"]["pronto_para_promocao"] is False
    assert "TESTE" in relatorio["proxima_acao_humana"]


def test_dev_usa_secret_ref_em_vez_de_url_literal() -> None:
    relatorio = validar(_registro_base())

    dev = relatorio["ambientes"]["dev"]
    assert dev["environment_url"] is None
    assert dev["url_secret_ref"] == "POWER_PLATFORM_ENVIRONMENT_URL"
    assert dev["papel"] == "origem"


def test_test_autorizado_fica_pronto_e_avanca_a_proxima_acao() -> None:
    relatorio = validar(_com_test_autorizado(_registro_base()))

    assert relatorio["valido"] is True
    assert relatorio["ambientes"]["test"]["pronto_para_promocao"] is True
    assert relatorio["ambientes"]["test"]["acao_humana_pendente"] is False
    assert "promocao real DEV -> TEST" in relatorio["proxima_acao_humana"]


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("environment_url", "https://orgtest01.crm2.dynamics.com/"),
        ("environment_url", "orgtest01.crm2.dynamics.com"),
        ("environment_url", "https://orgtest01.example.com"),
        ("environment_id", "nao-e-guid"),
        ("connection_id", "1234"),
        ("connection_reference_logical_name", "SemPrefixo"),
    ],
)
def test_formatos_invalidos_bloqueiam(campo: str, valor: str) -> None:
    registro = _com_test_autorizado(_registro_base())
    registro["ambientes"]["test"][campo] = valor

    relatorio = validar(registro)

    assert relatorio["valido"] is False
    assert any(campo in problema for problema in relatorio["problemas"])


def test_status_avancado_sem_connection_id_bloqueia() -> None:
    registro = _com_test_autorizado(_registro_base())
    registro["ambientes"]["test"]["connection_id"] = None

    relatorio = validar(registro)

    assert relatorio["valido"] is False
    assert any("exige connection_id" in problema for problema in relatorio["problemas"])


def test_promocao_validada_exige_evidencia() -> None:
    registro = _com_test_autorizado(_registro_base())
    registro["ambientes"]["test"]["status"] = "PROMOCAO_VALIDADA"

    relatorio = validar(registro)

    assert relatorio["valido"] is False
    assert any("evidencia_run_url" in problema for problema in relatorio["problemas"])


def test_dois_ambientes_apontando_para_o_mesmo_destino_bloqueiam() -> None:
    registro = _com_test_autorizado(_registro_base())
    registro["ambientes"]["prod"].update(
        {
            "status": "CONEXAO_AUTORIZADA",
            "environment_url": URL_TEST,
            "environment_id": GUID_ENV_PROD,
            "connection_id": GUID_CONN_PROD,
            "connection_reference_logical_name": REFERENCIA,
        }
    )

    relatorio = validar(registro)

    assert relatorio["valido"] is False
    assert any("environment_url duplicado" in problema for problema in relatorio["problemas"])


def test_prod_validado_antes_de_test_bloqueia_a_ordem() -> None:
    registro = _com_test_autorizado(_registro_base())
    registro["ambientes"]["prod"].update(
        {
            "status": "PROMOCAO_VALIDADA",
            "environment_url": URL_PROD,
            "environment_id": GUID_ENV_PROD,
            "connection_id": GUID_CONN_PROD,
            "connection_reference_logical_name": REFERENCIA,
            "evidencia_run_url": "https://github.example/actions/runs/1",
        }
    )

    relatorio = validar(registro)

    assert relatorio["valido"] is False
    assert any("DEV -> TEST -> PROD" in problema for problema in relatorio["problemas"])


def test_url_e_secret_ref_simultaneos_bloqueiam() -> None:
    registro = _com_test_autorizado(_registro_base())
    registro["ambientes"]["test"]["url_secret_ref"] = "OUTRO_SECRET"

    relatorio = validar(registro)

    assert relatorio["valido"] is False
    assert any("nunca os dois" in problema for problema in relatorio["problemas"])


def test_ambiente_ausente_e_registro_invalido() -> None:
    registro = _registro_base()
    del registro["ambientes"]["prod"]

    with pytest.raises(RegistroInvalido):
        validar(registro)


def test_conferencia_aceita_inputs_iguais_ao_registro() -> None:
    relatorio = validar(_com_test_autorizado(_registro_base()))

    divergencias = conferir_destino(
        relatorio,
        ambiente="test",
        url=URL_TEST.upper(),
        connection_id=GUID_CONN_TEST.upper(),
        connection_reference=REFERENCIA,
    )

    assert divergencias == []


def test_conferencia_detecta_destino_divergente() -> None:
    relatorio = validar(_com_test_autorizado(_registro_base()))

    divergencias = conferir_destino(
        relatorio,
        ambiente="test",
        url=URL_PROD,
        connection_id=GUID_CONN_TEST,
        connection_reference=REFERENCIA,
    )

    assert any("environment_url_destino diverge" in item for item in divergencias)


def test_conferencia_bloqueia_ambiente_nao_autorizado() -> None:
    relatorio = validar(_registro_base())

    divergencias = conferir_destino(
        relatorio,
        ambiente="test",
        url=URL_TEST,
        connection_id=GUID_CONN_TEST,
        connection_reference=REFERENCIA,
    )

    assert any("NAO_DEFINIDO" in item for item in divergencias)


def test_conferencia_nao_vaza_valor_do_registro_na_mensagem() -> None:
    relatorio = validar(_com_test_autorizado(_registro_base()))

    divergencias = conferir_destino(
        relatorio,
        ambiente="test",
        url=URL_TEST,
        connection_id=GUID_CONN_PROD,
        connection_reference=REFERENCIA,
    )

    assert divergencias
    assert all(GUID_CONN_TEST not in item for item in divergencias)
