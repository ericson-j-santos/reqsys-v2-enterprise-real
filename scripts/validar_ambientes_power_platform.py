#!/usr/bin/env python3
"""Valida o registro de ambientes Power Platform (DEV/TEST/PROD) fail-closed.

O registro (`config/power-platform/environments.json`) e a fonte unica dos dados que
hoje sao digitados a mao no `workflow_dispatch` de `teams-flow-bot-promotion.yml`.
Este validador cobre tres usos:

1. contrato de CI: o registro esta bem formado e internamente coerente;
2. gate de prontidao: `--exigir-pronto test` falha enquanto TEST nao estiver
   autorizado (blueprint itens 3 e 4);
3. guarda de drift: `--conferir-ambiente test --conferir-url ...` falha quando os
   inputs de uma promocao divergem do que foi registrado e revisado por PR.

Nenhum valor de segredo e lido, gravado ou impresso. `connection_id` e um
identificador de recurso do Power Platform, nao uma credencial.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"
CONTRACT = "power-platform-environment-registry"

AMBIENTES_ESPERADOS = ("dev", "test", "prod")

STATUS_PERMITIDOS = (
    "NAO_DEFINIDO",
    "DEFINIDO",
    "CONEXAO_AUTORIZADA",
    "PROMOCAO_VALIDADA",
)

STATUS_ORDEM = {status: indice for indice, status in enumerate(STATUS_PERMITIDOS)}

CAMPOS_AMBIENTE = (
    "papel",
    "status",
    "environment_url",
    "url_secret_ref",
    "environment_id",
    "github_environment",
    "connection_id",
    "connection_reference_logical_name",
    "evidencia_run_url",
    "observacao",
)

# https://orgXXXXXXXX.crm.dynamics.com, .crm2., .crm4.dynamics.com etc.
URL_DATAVERSE = re.compile(r"^https://[a-z0-9][a-z0-9-]*\.crm[0-9]*\.dynamics\.com$")
GUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
# Nome logico Dataverse: prefixo do publisher + "_" + nome.
LOGICAL_NAME = re.compile(r"^[a-z][a-z0-9]{1,7}_[A-Za-z0-9_]{1,60}$")


class RegistroInvalido(ValueError):
    """Registro malformado a ponto de nao ser possivel avaliar ambientes."""


def _texto(valor: Any) -> str | None:
    """Normaliza um campo textual opcional; devolve None quando vazio."""
    if valor is None:
        return None
    if not isinstance(valor, str):
        raise RegistroInvalido("campo textual com tipo invalido")
    limpo = valor.strip()
    return limpo or None


def _carregar(caminho: Path) -> dict[str, Any]:
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except FileNotFoundError as erro:
        raise RegistroInvalido(f"registro nao encontrado: {caminho}") from erro
    except json.JSONDecodeError as erro:
        raise RegistroInvalido(f"registro nao e JSON valido: {erro}") from erro
    if not isinstance(dados, dict):
        raise RegistroInvalido("registro deve ser um objeto JSON")
    return dados


def _validar_ambiente(nome: str, bruto: Any) -> tuple[dict[str, Any], list[str]]:
    """Avalia um ambiente isolado. Devolve o resumo e a lista de problemas."""
    problemas: list[str] = []

    if not isinstance(bruto, dict):
        raise RegistroInvalido(f"ambiente '{nome}' deve ser um objeto JSON")

    desconhecidos = sorted(set(bruto) - set(CAMPOS_AMBIENTE))
    if desconhecidos:
        problemas.append(f"{nome}: campos desconhecidos {desconhecidos}")

    try:
        url = _texto(bruto.get("environment_url"))
        url_secret_ref = _texto(bruto.get("url_secret_ref"))
        environment_id = _texto(bruto.get("environment_id"))
        connection_id = _texto(bruto.get("connection_id"))
        connection_reference = _texto(bruto.get("connection_reference_logical_name"))
        evidencia = _texto(bruto.get("evidencia_run_url"))
    except RegistroInvalido as erro:
        raise RegistroInvalido(f"ambiente '{nome}': {erro}") from erro

    status = bruto.get("status")
    if status not in STATUS_PERMITIDOS:
        problemas.append(f"{nome}: status invalido {status!r}; esperado um de {list(STATUS_PERMITIDOS)}")
        status = "NAO_DEFINIDO"

    papel = bruto.get("papel")
    if papel not in ("origem", "destino"):
        problemas.append(f"{nome}: papel invalido {papel!r}; esperado 'origem' ou 'destino'")

    if url is not None and not URL_DATAVERSE.match(url):
        problemas.append(
            f"{nome}: environment_url {url!r} fora do formato "
            "https://<org>.crm<N>.dynamics.com (sem barra final)"
        )
    if environment_id is not None and not GUID.match(environment_id):
        problemas.append(f"{nome}: environment_id {environment_id!r} nao e um GUID")
    if connection_id is not None and not GUID.match(connection_id):
        problemas.append(f"{nome}: connection_id {connection_id!r} nao e um GUID")
    if connection_reference is not None and not LOGICAL_NAME.match(connection_reference):
        problemas.append(
            f"{nome}: connection_reference_logical_name {connection_reference!r} nao parece "
            "um nome logico Dataverse (<prefixo>_<nome>)"
        )
    if url is not None and url_secret_ref is not None:
        problemas.append(f"{nome}: defina environment_url OU url_secret_ref, nunca os dois")

    tem_endereco = url is not None or url_secret_ref is not None

    # Coerencia entre status declarado e campos efetivamente preenchidos.
    if STATUS_ORDEM[status] >= STATUS_ORDEM["DEFINIDO"] and not tem_endereco:
        problemas.append(f"{nome}: status {status} exige environment_url ou url_secret_ref")
    if STATUS_ORDEM[status] >= STATUS_ORDEM["CONEXAO_AUTORIZADA"]:
        if connection_id is None:
            problemas.append(f"{nome}: status {status} exige connection_id")
        if connection_reference is None:
            problemas.append(f"{nome}: status {status} exige connection_reference_logical_name")
    if status == "PROMOCAO_VALIDADA" and evidencia is None:
        problemas.append(f"{nome}: status PROMOCAO_VALIDADA exige evidencia_run_url")

    resumo = {
        "ambiente": nome,
        "papel": papel,
        "status": status,
        "environment_url": url,
        "url_secret_ref": url_secret_ref,
        "environment_id": environment_id,
        "connection_id": connection_id,
        "connection_reference_logical_name": connection_reference,
        "evidencia_run_url": evidencia,
        "definido": tem_endereco and environment_id is not None,
        "pronto_para_promocao": (
            STATUS_ORDEM[status] >= STATUS_ORDEM["CONEXAO_AUTORIZADA"]
            and tem_endereco
            and connection_id is not None
            and connection_reference is not None
        ),
        "acao_humana_pendente": STATUS_ORDEM[status] < STATUS_ORDEM["CONEXAO_AUTORIZADA"],
    }
    return resumo, problemas


def _validar_unicidade(ambientes: dict[str, dict[str, Any]]) -> list[str]:
    """Impede que dois ambientes logicos apontem para o mesmo destino real."""
    problemas: list[str] = []
    for campo in ("environment_url", "environment_id", "connection_id"):
        vistos: dict[str, str] = {}
        for nome in AMBIENTES_ESPERADOS:
            valor = ambientes[nome][campo]
            if valor is None:
                continue
            chave = valor.lower()
            if chave in vistos:
                problemas.append(
                    f"{campo} duplicado entre '{vistos[chave]}' e '{nome}': "
                    "ambientes logicos distintos nao podem apontar para o mesmo recurso"
                )
            else:
                vistos[chave] = nome
    return problemas


def validar(registro: dict[str, Any]) -> dict[str, Any]:
    """Valida o registro inteiro e devolve o relatorio sanitizado."""
    problemas: list[str] = []

    if registro.get("schema_version") != SCHEMA_VERSION:
        problemas.append(
            f"schema_version {registro.get('schema_version')!r} diferente do esperado {SCHEMA_VERSION!r}"
        )

    principios = registro.get("principios")
    if not isinstance(principios, dict) or principios.get("armazena_segredo") is not False:
        problemas.append("principios.armazena_segredo deve ser explicitamente false")

    bruto_ambientes = registro.get("ambientes")
    if not isinstance(bruto_ambientes, dict):
        raise RegistroInvalido("registro deve conter o objeto 'ambientes'")

    faltando = sorted(set(AMBIENTES_ESPERADOS) - set(bruto_ambientes))
    if faltando:
        raise RegistroInvalido(f"ambientes ausentes no registro: {faltando}")
    sobrando = sorted(set(bruto_ambientes) - set(AMBIENTES_ESPERADOS))
    if sobrando:
        problemas.append(f"ambientes nao previstos no registro: {sobrando}")

    ambientes: dict[str, dict[str, Any]] = {}
    for nome in AMBIENTES_ESPERADOS:
        resumo, achados = _validar_ambiente(nome, bruto_ambientes[nome])
        ambientes[nome] = resumo
        problemas.extend(achados)

    problemas.extend(_validar_unicidade(ambientes))

    if ambientes["dev"]["papel"] != "origem":
        problemas.append("dev deve ter papel 'origem'")

    # PROD nao pode ser promovido antes de TEST ter evidencia real.
    if (
        ambientes["prod"]["status"] == "PROMOCAO_VALIDADA"
        and ambientes["test"]["status"] != "PROMOCAO_VALIDADA"
    ):
        problemas.append("prod nao pode estar PROMOCAO_VALIDADA antes de test (ordem DEV -> TEST -> PROD)")

    return {
        "schema_version": SCHEMA_VERSION,
        "contract": CONTRACT,
        "valido": not problemas,
        "decision": "validated" if not problemas else "blocked",
        "problemas": problemas,
        "ambientes": ambientes,
        "proxima_acao_humana": _proxima_acao(ambientes),
        "secret_value_logged": False,
        "production_touched": False,
    }


def _proxima_acao(ambientes: dict[str, dict[str, Any]]) -> str:
    if not ambientes["test"]["definido"]:
        return "Definir o ambiente Power Platform de TESTE e registrar environment_url + environment_id."
    if not ambientes["test"]["pronto_para_promocao"]:
        return "Autorizar a conexao Microsoft Teams no ambiente de TESTE e registrar connection_id + connection_reference_logical_name."
    if ambientes["test"]["status"] != "PROMOCAO_VALIDADA":
        return "Executar a primeira promocao real DEV -> TEST e registrar evidencia_run_url."
    if not ambientes["prod"]["pronto_para_promocao"]:
        return "Repetir a definicao de ambiente e a autorizacao Teams para PROD."
    if ambientes["prod"]["status"] != "PROMOCAO_VALIDADA":
        return "Executar a promocao governada TEST -> PROD."
    return "Nenhuma: DEV, TEST e PROD registrados e validados."


def conferir_destino(
    relatorio: dict[str, Any],
    *,
    ambiente: str,
    url: str | None,
    connection_id: str | None,
    connection_reference: str | None,
) -> list[str]:
    """Compara os inputs de uma promocao com o que o registro declara."""
    if ambiente not in relatorio["ambientes"]:
        return [f"ambiente '{ambiente}' nao existe no registro"]

    registrado = relatorio["ambientes"][ambiente]
    divergencias: list[str] = []

    if not registrado["pronto_para_promocao"]:
        divergencias.append(
            f"ambiente '{ambiente}' esta em status {registrado['status']}; "
            "promocao exige CONEXAO_AUTORIZADA ou superior no registro"
        )

    comparacoes = (
        ("environment_url_destino", url, registrado["environment_url"]),
        ("connection_id_destino", connection_id, registrado["connection_id"]),
        (
            "connection_reference_logical_name",
            connection_reference,
            registrado["connection_reference_logical_name"],
        ),
    )
    for rotulo, informado, esperado in comparacoes:
        informado = informado.strip() if isinstance(informado, str) else informado
        if not informado:
            continue
        if esperado is None:
            divergencias.append(f"{rotulo} informado mas ausente no registro do ambiente '{ambiente}'")
        elif informado.casefold() != esperado.casefold():
            divergencias.append(
                f"{rotulo} diverge do registro do ambiente '{ambiente}' "
                "(revise o registro por PR antes de promover)"
            )
    return divergencias


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registro", type=Path, default=Path("config/power-platform/environments.json"))
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--exigir-pronto",
        action="append",
        default=[],
        choices=sorted(AMBIENTES_ESPERADOS),
        help="Falha quando o ambiente indicado nao estiver pronto para promocao.",
    )
    parser.add_argument("--conferir-ambiente", choices=sorted(AMBIENTES_ESPERADOS))
    parser.add_argument("--conferir-url", default="")
    parser.add_argument("--conferir-connection-id", default="")
    parser.add_argument("--conferir-connection-reference", default="")
    args = parser.parse_args()

    try:
        relatorio = validar(_carregar(args.registro))
    except RegistroInvalido as erro:
        print(f"::error::Registro de ambientes Power Platform invalido: {erro}")
        return 1

    divergencias: list[str] = []
    if args.conferir_ambiente:
        divergencias = conferir_destino(
            relatorio,
            ambiente=args.conferir_ambiente,
            url=args.conferir_url,
            connection_id=args.conferir_connection_id,
            connection_reference=args.conferir_connection_reference,
        )
        relatorio["conferencia"] = {
            "ambiente": args.conferir_ambiente,
            "divergencias": divergencias,
            "coerente": not divergencias,
        }

    nao_prontos = [nome for nome in args.exigir_pronto if not relatorio["ambientes"][nome]["pronto_para_promocao"]]
    relatorio["exigidos_prontos"] = sorted(set(args.exigir_pronto))
    relatorio["exigidos_nao_prontos"] = nao_prontos

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for problema in relatorio["problemas"]:
        print(f"::error::{problema}")
    for divergencia in divergencias:
        print(f"::error::{divergencia}")
    for nome in nao_prontos:
        print(
            f"::error::ambiente '{nome}' ainda nao esta pronto para promocao "
            f"(status {relatorio['ambientes'][nome]['status']})"
        )

    print(f"Registro Power Platform: decision={relatorio['decision']}")
    print(f"Proxima acao humana: {relatorio['proxima_acao_humana']}")

    if relatorio["problemas"] or divergencias or nao_prontos:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
