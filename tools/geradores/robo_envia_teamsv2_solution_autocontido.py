#!/usr/bin/env python3
"""ReqSys robo_envia_teamsv2 -- solucao real do Power Automate, autocontida.

Este gerador NAO reimplementa a logica do flow em Python (isso ja existe em
tools/geradores/robo_envia_teamsv1_autocontido.py para o v1, e nao se aplica
aqui da mesma forma -- ver observacao abaixo). Ele materializa, a partir de
um payload base64 embutido no proprio arquivo, o pacote de solucao real
exportado do Power Automate (`pac solution export`), byte a byte identico ao
capturado ao vivo. Objetivo: ter o artefato binario versionado como codigo
Python puro (sem depender de um .zip binario solto no repositorio, e sem
depender de acesso ao Dataverse para reproduzir/auditar o conteudo).

Origem do payload
------------------
Exportado ao vivo do Dataverse em 2026-07-27/28 pelo usuario via Maker
Portal / `pac solution export`, ambiente **tieri (default)**
(org `https://orga258f260.crm2.dynamics.com/`, tenant
`tieri659.onmicrosoft.com`) -- MESMO ambiente onde `robo_envia_teamsv1`
vive (ver tools/geradores/robo_envia_teamsv1_autocontido.py), NAO o
ambiente `reqsys-power-platform-dev`/"ReqSys Dev" usado por
`scripts/update_teams_v2_adaptive_card.py`. Duas instancias do flow
`robo_envia_teamsv2` existem em ambientes diferentes -- esta e a que
`TEAMS_WEBHOOK_URL` (usado por `.github/workflows/teams-commit-notification.yml`)
realmente invoca em producao; a outra ("ReqSys Dev") e usada pelo pipeline
de ativacao `teams-notification-dev-import.yml`. Ver
`docs/servicos/teams-commit-notification.md` e a memoria de sessao
"teams_webhook_url_real_target_tieri" para o historico completo dessa
confusao (resolvida em 2026-07-28).

Analise do conteudo (solution.xml / customizations.xml / Workflows/*.json)
----------------------------------------------------------------------------
- `solution.xml`: `UniqueName=robo_envia_teamsv2`, `Version=1.0.0.3`,
  `Managed=0` (unmanaged), publisher `reqsys` (prefixo `reqsys`),
  `RootComponent type=29` (Workflow/cloud flow) `id={df4fa822-...}` --
  **atencao**: esse GUID e o `workflowid` no Dataverse do AMBIENTE ONDE
  ESTE ZIP FOI EXPORTADO. Nao assumir que e o mesmo `workflowid` em outro
  ambiente (ver o gotcha de "GUID de trigger URL != workflowid" ja
  documentado no v1).
- `customizations.xml`: 1 `Workflow` (`Category=5`=cloud flow,
  `StateCode=1`/`StatusCode=2`=ativo), 1 `connectionreference`
  (`new_sharedteams_0b6e2` -> conector `shared_teams`/Microsoft Teams).
- `Workflows/robo_envia_teamsv2-....json` (`clientdata`, ~14.5KB):
  - Trigger `manual`: `Request`/`kind=TeamsWebhook`, schema aceita o
    envelope padrao de "Post card"
    (`{type, attachments:[{contentType, content:{$schema,type,version,body}}]}`)
    -- schema documental, o flow na pratica le os campos via
    `triggerBody()?[...]` (ver abaixo), nao esse envelope.
  - `Scope_TRY` -> `Analisar_JSON` (ParseJson, campos obrigatorios
    `to,title,content,signature`, opcionais `stampDate,correlationId`)
    -> `Compose_CorrelationId_Final` -> `Condição_` (If):
    `to contem '@' E len(content)>0 E len(title)>0`.
    - ramo true: `Compose_StampDate` -> `Compose_Message` ->
      `Postar_cartão_em_um_chat_ou_canal` (`shared_teams`/
      `PostCardToConversation`, poster=`Flow bot`,
      location=`Chat with Flow bot`, `body/recipient` via
      `toLower(trim(body('Analisar_JSON')?['to']))`) -> `Resposta__1` (200).
    - ramo else: `Resposta_` (400, payload invalido).
  - `Scope_CATCH` -> `Resposta` (500).
  - `body/messageBody` da acao de post: **CORRIGIDO** nesta exportacao --
    usa `triggerBody()?['title']`/`content`/`signature`/`stampDate`/
    `correlationId` (nao mais um card estatico hardcoded tipo
    "Requisito #482"), cada valor passando por uma cadeia `replace()`
    que escapa barra invertida/aspas/CR/LF antes de entrar no JSON do
    Adaptive Card por `concat()` -- mesmo padrao de escaping aplicado
    (por automacao, PR #1043) na copia "ReqSys Dev" deste flow, so que
    aqui feito manualmente no Maker Portal a partir de uma expressao
    fornecida em sessao de chat. Suporta ainda `triggerBody()?['adaptiveCard']`
    como override explicito (se o chamador mandar um card pronto, ele
    e usado no lugar do card generico).

Uso
---
    python robo_envia_teamsv2_solution_autocontido.py materializar --output caminho.zip
    python robo_envia_teamsv2_solution_autocontido.py extrair --output-dir pasta/
    python robo_envia_teamsv2_solution_autocontido.py self-test
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

SOLUTION_UNIQUE_NAME = "robo_envia_teamsv2"
SOLUTION_VERSION = "1.0.0.3"
WORKFLOW_ID_ORIGEM = "df4fa822-0c89-f111-8076-6045bd3ac4b4"
AMBIENTE_ORIGEM = "tieri (default)"
SHA256_ESPERADO = "e33ca3012016ec3c7673cadf5fe85aca024427872dd58001fe07e515deb22986"

# Payload base64 do pacote de solucao real exportado (robo_envia_teamsv2_1_0_0_3.zip).
_PAYLOAD_B64 = (
    "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"
    "J30LdlKrZmu13fZfDNg9GfDJgE8GfDJgneZkwP9jwEekvJNZzUuU98C5mnI0CgZMVbQ13FCHW617aRo0HJs/w+VwSUau27OD"
    "0WVv6ThOb2RfnPfO7eHZIhyQYLgY/jKNBazJhnIxNu3qdVE7pDejUmLnXkMCLES/olDcGrEr29fhwt2OfyJMfgNQSwMEFAAC"
    "AAgAzAP8XIIGjXfmDAAANjoAAEYAHABXb3JrZmxvd3Mvcm9ib19lbnZpYV90ZWFtc3YyLURGNEZBODIyLTBDODktRjExMS04"
    "MDc2LTYwNDVCRDNBQzRCNC5qc29uIKIYACigFAAAAAAAAAAAAAAAAAAAAAAAAAAAAO1bS5PbuBG+b9X+BxbjlGaqxBElUg/O"
    "Oo7HY3vtLY/X5ZndVLJyTYEEKGFNEVw+5llTtf8hOeaylUNOOeWW6/yT/SVpgJT4EEFR8mNziOyaoYhGA91oNL5u9Nx++YWi"
    "qEHIAhLGlETqoXLLX8FLh/k+cWLK/LfEJSHxnWIzEERzFBJ8HhO0KDVAU5j4MV2QU5aEDoE2lSxsgjHBardAlY9Q7l4/+Cs2"
    "ow7yXqOF4OiTy/N0BmIC57o9IgM1Z3JXHAkFdG0IP2NUEqPQf/mYPSz5qZi41KfVWasPImdOFohznMdxEB32eumbgwXy0Yws"
    "iB8foJskJAcOW/RA5RcUkzDqnVAnZBFz4wMhYdYr6g30/kjT4X+/d8nC967HLvOhD36MmP+7XJtcYTGM8D1wTGem9g90/q9A"
    "E6AQZI6BpLJcD1ASz6E36Ld2NWBclHjx98hLuMpui7qF5vg6EJo8JQ6I9639I6ycbCUe5Csb7TrO+girtcqFjUM6m62LCouR"
    "IG9tZFALwihG1QZo4ltDqOUko3mJ+SQs1HdcPBloiIzHmqmbA83q6642GtsIDL0/GE8stchKIsxb8lNColgtt76nvhjljFvl"
    "n4g9Z+x9hYT6QRKv6TCX/Ki0pmfZcEeeV+bDN/LSciucCrNkqcq7awR1rqOOQ01TgX0Ec/Zn6jrN3dqIfDfHMXLmfENJBi1w"
    "RmGIrtfnLWhoTKqeayvhW6ogI8t26FmDPirjSrWSfup0Ux6r5TjN8m0hoyB9IDcnyfgb5OQfuaxFTp9vwIuVn/18Y9oMX28x"
    "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"
)


def _payload_bytes() -> bytes:
    return base64.b64decode(_PAYLOAD_B64)


def verificar_integridade() -> None:
    digest = hashlib.sha256(_payload_bytes()).hexdigest()
    if digest != SHA256_ESPERADO:
        raise ValueError(f"SHA256 do payload embutido não confere: esperado {SHA256_ESPERADO}, obtido {digest}")


def materializar(output_path: str) -> Path:
    """Grava os bytes exatos do pacote de solução real em output_path."""
    verificar_integridade()
    destino = Path(output_path)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(_payload_bytes())
    return destino


def extrair(output_dir: str) -> list[str]:
    """Extrai o conteúdo do pacote (solution.xml, customizations.xml, Workflows/*.json)."""
    verificar_integridade()
    destino = Path(output_dir)
    destino.mkdir(parents=True, exist_ok=True)
    nomes: list[str] = []
    with zipfile.ZipFile(io.BytesIO(_payload_bytes())) as pacote:
        pacote.extractall(destino)
        nomes = pacote.namelist()
    return nomes


def inspecionar_workflow() -> dict[str, Any]:
    """Lê Workflows/*.json de dentro do payload embutido (sem gravar nada em
    disco) e devolve um resumo estrutural — útil para auditoria/CI."""
    verificar_integridade()
    with zipfile.ZipFile(io.BytesIO(_payload_bytes())) as pacote:
        (workflow_entry,) = [n for n in pacote.namelist() if n.startswith("Workflows/") and n.endswith(".json")]
        clientdata = json.loads(pacote.read(workflow_entry).decode("utf-8"))
    definicao = clientdata["properties"]["definition"]
    scope_try = definicao["actions"]["Scope_TRY"]["actions"]
    condicao = scope_try["Condição_"]
    post_action = condicao["actions"]["Postar_cartão_em_um_chat_ou_canal"]
    return {
        "workflow_entry": workflow_entry,
        "trigger_kind": definicao["triggers"]["manual"]["kind"],
        "top_level_actions": sorted(definicao["actions"].keys()),
        "scope_try_actions": sorted(scope_try.keys()),
        "condicao_true_actions": sorted(condicao["actions"].keys()),
        "condicao_else_actions": sorted(condicao.get("else", {}).get("actions", {}).keys()),
        "post_action_operation_id": post_action["inputs"]["host"]["operationId"],
        "message_body_usa_static_card": "Requisito #482" in post_action["inputs"]["parameters"]["body/messageBody"],
        "message_body_usa_trigger_body": "triggerBody()?['title']" in post_action["inputs"]["parameters"]["body/messageBody"],
    }


def self_test() -> dict[str, Any]:
    verificar_integridade()
    resumo = inspecionar_workflow()
    assert resumo["trigger_kind"] == "TeamsWebhook"
    assert resumo["post_action_operation_id"] == "PostCardToConversation"
    assert resumo["message_body_usa_static_card"] is False, "regressão: card estático voltou a aparecer no payload embutido"
    assert resumo["message_body_usa_trigger_body"] is True
    assert resumo["condicao_else_actions"] == ["Resposta_"]

    # materializar + extrair de verdade (round-trip completo), sem deixar lixo
    with zipfile.ZipFile(io.BytesIO(_payload_bytes())) as pacote:
        nomes = set(pacote.namelist())
    esperado = {
        "customizations.xml",
        "solution.xml",
        "[Content_Types].xml",
        resumo["workflow_entry"],
    }
    assert esperado == nomes, f"conteúdo inesperado no pacote: {nomes}"

    return {"passed": 6, "status": "ok", "sha256": SHA256_ESPERADO}


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    sub.add_parser("self-test")
    sub.add_parser("inspecionar")
    materializar_cmd = sub.add_parser("materializar")
    materializar_cmd.add_argument("--output", required=True)
    extrair_cmd = sub.add_parser("extrair")
    extrair_cmd.add_argument("--output-dir", required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    if args.command == "self-test":
        print(json.dumps(self_test(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "inspecionar":
        print(json.dumps(inspecionar_workflow(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "materializar":
        destino = materializar(args.output)
        print(json.dumps({"status": "ok", "output": str(destino), "sha256": SHA256_ESPERADO}, ensure_ascii=False, indent=2))
        return 0
    nomes = extrair(args.output_dir)
    print(json.dumps({"status": "ok", "output_dir": args.output_dir, "arquivos": nomes}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
