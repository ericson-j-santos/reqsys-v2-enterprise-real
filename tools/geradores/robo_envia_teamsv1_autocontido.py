#!/usr/bin/env python3
"""ReqSys robo_envia_teamsv1 autocontido -- tradução fiel do flow real do Power Automate.

Fonte: Dataverse `workflows.clientdata` (workflowid=143fcbeb-d47b-f111-ab0e-000d3ac172b1,
ambiente "tieri (default)"), extraída ao vivo via Dataverse Web API em 2026-07-14.
Clone manual ("Save As") de `robo_envia_teams20260108v2`, hoje owner ativo do canal
flow_bot do Teams Messaging Gateway (ver docs/architecture/teams-messaging-gateway.md).

Cada função abaixo replica 1:1 uma ação real do designer (nome indicado no comentário).
A ÚNICA exceção é "Postar_mensagem_em_um_chat_ou_canal__" (conector `shared_teams` /
`PostMessageToConversation`, poster="Flow bot", location="Chat with Flow bot"): essa
operação NÃO tem API pública fora do runtime de conectores do Power Platform -- a
Microsoft não permite postar como "Flow bot" em "Chat with Flow bot" via Graph/REST
(confirmado e documentado no gateway). Por isso este módulo NUNCA reimplementa esse
passo -- ele sempre delega para o próprio flow já publicado, via
TEAMS_FLOW_BOT_TRIGGER_URL, e só relata `"ok": true"` quando essa chamada HTTP real
de fato confirmou sucesso. `--dry-run` nunca produz o mesmo formato de uma entrega
real (marcado explicitamente como "planned"), justamente para não fingir envio.

Configuração:
- TEAMS_FLOW_BOT_TRIGGER_URL: Trigger URL real do flow `robo_envia_teamsv1`.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping
from zoneinfo import ZoneInfo

FUSO_HORARIO = ZoneInfo("America/Sao_Paulo")  # equivalente a "E. South America Standard Time"
CAMPOS_OBRIGATORIOS = ("to", "title", "content", "signature")


class FluxoError(RuntimeError):
    pass


@dataclass(frozen=True)
class FluxoConfig:
    trigger_url: str | None = None
    timeout_seconds: int = 15
    max_attempts: int = 3

    @classmethod
    def from_env(cls) -> "FluxoConfig":
        return cls(
            trigger_url=os.getenv("TEAMS_FLOW_BOT_TRIGGER_URL"),
            timeout_seconds=int(os.getenv("HTTP_TIMEOUT_SECONDS", "15")),
            max_attempts=int(os.getenv("HTTP_MAX_ATTEMPTS", "3")),
        )

    @property
    def configurado(self) -> bool:
        return bool(self.trigger_url)


class HttpClient:
    """Cliente HTTP com retry -- mesma política de tools/geradores/teams_graph_gateway_autocontido.py."""

    def __init__(self, config: FluxoConfig) -> None:
        self.config = config

    @staticmethod
    def safe_json(raw: str) -> dict[str, Any]:
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except json.JSONDecodeError:
            return {"message": raw[:1000]}

    def post(self, url: str, payload: Mapping[str, Any]) -> tuple[int, dict[str, Any]]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Accept": "application/json", "Content-Type": "application/json; charset=utf-8"}
        last_error: Exception | None = None
        for attempt in range(1, self.config.max_attempts + 1):
            request = urllib.request.Request(url, data=body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                    raw = response.read().decode("utf-8", errors="replace")
                    return int(response.status), self.safe_json(raw)
            except urllib.error.HTTPError as exc:
                raw = exc.read().decode("utf-8", errors="replace")
                if exc.code not in {429, 500, 502, 503, 504} or attempt == self.config.max_attempts:
                    return int(exc.code), self.safe_json(raw)
                retry_after = int(exc.headers.get("Retry-After", "1"))
                time.sleep(min(retry_after, 5))
                last_error = exc
            except (urllib.error.URLError, TimeoutError) as exc:
                last_error = exc
                if attempt == self.config.max_attempts:
                    break
                time.sleep(min(2 ** (attempt - 1), 4))
        raise FluxoError(f"Falha de comunicação após {self.config.max_attempts} tentativas: {last_error}")


def _formatar_stamp(momento: datetime) -> str:
    """Reproduz convertTimeZone(..., 'yyyy-MM-ddTHH:mm:sszzz'): offset com dois-pontos."""
    texto = momento.astimezone(FUSO_HORARIO).strftime("%Y-%m-%dT%H:%M:%S%z")
    return f"{texto[:-2]}:{texto[-2:]}"


def _agora_formatado() -> str:
    return _formatar_stamp(datetime.now(tz=ZoneInfo("UTC")))


def analisar_json(corpo: Mapping[str, Any]) -> dict[str, Any]:
    """Ação 'Analisar_JSON' (ParseJson) -- required: to, title, content, signature."""
    ausentes = [campo for campo in CAMPOS_OBRIGATORIOS if not corpo.get(campo)]
    if ausentes:
        raise FluxoError(f"Campos obrigatórios ausentes no payload: {ausentes}")
    return {
        "to": corpo.get("to"),
        "title": corpo.get("title"),
        "content": corpo.get("content"),
        "signature": corpo.get("signature"),
        "stampDate": corpo.get("stampDate"),
        "correlationId": corpo.get("correlationId"),
    }


def compose_correlation_id() -> str:
    """Ação 'Compose_CorrelationId': @guid()."""
    return str(uuid.uuid4())


def compose_correlation_id_final(dados: Mapping[str, Any], correlation_id_gerado: str) -> str:
    """Ação 'Compose_CorrelationId_Final': prioriza o correlationId recebido no payload."""
    recebido = dados.get("correlationId")
    return recebido if recebido else correlation_id_gerado


def condicao(dados: Mapping[str, Any]) -> bool:
    """Expressão do 'Condição_' (If): to contém '@' E len(content)>0 E len(title)>0."""
    to = dados.get("to") or ""
    content = dados.get("content") or ""
    title = dados.get("title") or ""
    return "@" in to and len(content) > 0 and len(title) > 0


def compose_stamp_date(dados: Mapping[str, Any]) -> str:
    """Ação 'Compose_StampDate': usa stampDate do payload, senão hora atual (fuso BR)."""
    return dados.get("stampDate") or _agora_formatado()


def compose_message(dados: Mapping[str, Any], stamp_date: str, correlation_id_final: str) -> str:
    """Ação 'Compose_Message': HTML idêntico ao concat() do flow."""
    conteudo_html = (dados.get("content") or "").replace("\n", "<br/>")
    return (
        f"<b>{dados.get('title')}</b><br/>"
        "<hr/>"
        f"{conteudo_html}<br/><br/>"
        f"<i>— {dados.get('signature')}</i><br/>"
        f'<span style="color:gray;">{stamp_date}</span><br/>'
        f'<span style="color:gray;">CorrelationId: {correlation_id_final}</span>'
    )


def montar_parametros_mensagem(dados: Mapping[str, Any], mensagem_html: str) -> dict[str, Any]:
    """Parâmetros de 'Postar_mensagem_em_um_chat_ou_canal__' (poster/location fixos no flow)."""
    return {
        "poster": "Flow bot",
        "location": "Chat with Flow bot",
        "recipient": (dados.get("to") or "").strip().lower(),
        "messageBody": f'<p class="editor-paragraph">{mensagem_html}<br></p><br>',
    }


def resposta_sucesso(dados: Mapping[str, Any]) -> dict[str, Any]:
    """Ação 'Resposta__1' (200) -- só é retornada após confirmação HTTP real de envio."""
    return {
        "ok": True,
        "to": dados.get("to"),
        "titleLength": len(dados.get("title") or ""),
        "contentLength": len(dados.get("content") or ""),
        "stamp": _agora_formatado(),
    }


def resposta_payload_invalido(dados: Mapping[str, Any]) -> dict[str, Any]:
    """Ação 'Resposta_' (400, ramo 'else' da condição)."""
    return {
        "ok": False,
        "error": "Payload inválido",
        "to": dados.get("to"),
        "titleLength": len(dados.get("title") or ""),
        "contentLength": len(dados.get("content") or ""),
        "stamp": _agora_formatado(),
    }


def resposta_falha_interna(correlation_id: str, detalhe: str | None = None) -> dict[str, Any]:
    """Ação 'Resposta' dentro de 'Scope_CATCH' (500)."""
    corpo: dict[str, Any] = {"ok": False, "error": "Falha interna no envio", "correlationId": correlation_id}
    if detalhe:
        corpo["detalhe"] = detalhe
    return corpo


@dataclass(frozen=True)
class ResultadoFluxo:
    status_code: int
    body: dict[str, Any]
    enviado: bool  # True somente se a chamada HTTP real ao Power Automate confirmou sucesso

    def as_dict(self) -> dict[str, Any]:
        return {"statusCode": self.status_code, "body": self.body, "enviado": self.enviado}


class RoboEnviaTeamsV1:
    def __init__(self, config: FluxoConfig | None = None, http: HttpClient | None = None) -> None:
        self.config = config or FluxoConfig.from_env()
        self.http = http or HttpClient(self.config)

    def status(self) -> dict[str, Any]:
        return {
            "service": "robo-envia-teamsv1-autocontido",
            "trigger_configurado": self.config.configurado,
            "workflowid_origem": "143fcbeb-d47b-f111-ab0e-000d3ac172b1",
        }

    def postar_mensagem_teams(self, parametros_mensagem: Mapping[str, Any]) -> tuple[int, dict[str, Any]]:
        """Executa de fato 'Postar_mensagem_em_um_chat_ou_canal__' -- sempre via HTTP real
        contra o flow publicado. Nunca simula sucesso localmente."""
        if not self.config.configurado:
            raise FluxoError(
                "TEAMS_FLOW_BOT_TRIGGER_URL não configurada -- necessária para executar de "
                "verdade o passo do conector Teams ('Flow bot' / 'Chat with Flow bot'), que "
                "não tem API pública fora do Power Automate"
            )
        return self.http.post(self.config.trigger_url, parametros_mensagem)  # type: ignore[arg-type]

    def executar(self, payload: Mapping[str, Any], dry_run: bool = False) -> ResultadoFluxo:
        """Trigger 'manual' (Request, kind=TeamsWebhook) -- Scope_TRY / Scope_CATCH."""
        correlation_id_gerado = compose_correlation_id()
        try:
            dados = analisar_json(payload)
            correlation_id_final = compose_correlation_id_final(dados, correlation_id_gerado)

            if not condicao(dados):
                return ResultadoFluxo(400, resposta_payload_invalido(dados), enviado=False)

            stamp_date = compose_stamp_date(dados)
            mensagem_html = compose_message(dados, stamp_date, correlation_id_final)
            parametros_mensagem = montar_parametros_mensagem(dados, mensagem_html)

            if dry_run:
                return ResultadoFluxo(
                    0,
                    {
                        "planned": True,
                        "parametros_mensagem": parametros_mensagem,
                        "correlationId": correlation_id_final,
                    },
                    enviado=False,
                )

            status_code, resposta_http = self.postar_mensagem_teams(parametros_mensagem)
            if not (200 <= status_code < 300):
                detalhe = f"HTTP {status_code} do flow publicado: {resposta_http}"
                return ResultadoFluxo(500, resposta_falha_interna(correlation_id_gerado, detalhe), enviado=False)

            return ResultadoFluxo(200, resposta_sucesso(dados), enviado=True)

        except FluxoError as exc:
            return ResultadoFluxo(500, resposta_falha_interna(correlation_id_gerado, str(exc)), enviado=False)


def self_test() -> dict[str, Any]:
    """Bateria mínima executável sem rede -- espelha o self-test de teams_graph_gateway_autocontido.py."""
    fluxo = RoboEnviaTeamsV1(FluxoConfig())
    base = {"to": "fulano@tieri659.onmicrosoft.com", "title": "Aviso", "content": "corpo", "signature": "ReqSys"}

    planejado = fluxo.executar(base, dry_run=True)
    assert planejado.enviado is False and planejado.body.get("planned") is True

    invalido = fluxo.executar({**base, "to": "sem-arroba"}, dry_run=True)
    assert invalido.status_code == 400 and invalido.enviado is False

    faltando = fluxo.executar({"to": base["to"], "title": "Aviso"}, dry_run=False)
    assert faltando.status_code == 500 and faltando.enviado is False

    sem_config = fluxo.executar(base, dry_run=False)
    assert sem_config.status_code == 500 and sem_config.enviado is False
    assert "TEAMS_FLOW_BOT_TRIGGER_URL" in sem_config.body["detalhe"]

    return {"passed": 4, "status": "ok"}


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    sub = root.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("self-test")
    enviar = sub.add_parser("enviar")
    enviar.add_argument("--to", required=True)
    enviar.add_argument("--title", required=True)
    enviar.add_argument("--content", required=True)
    enviar.add_argument("--signature", default="ReqSys")
    enviar.add_argument("--correlation-id")
    enviar.add_argument("--dry-run", action="store_true")
    return root


def main() -> int:
    args = parser().parse_args()
    fluxo = RoboEnviaTeamsV1()
    if args.command == "status":
        print(json.dumps(fluxo.status(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "self-test":
        print(json.dumps(self_test(), ensure_ascii=False, indent=2))
        return 0

    payload = {
        "to": args.to,
        "title": args.title,
        "content": args.content,
        "signature": args.signature,
        "correlationId": args.correlation_id,
    }
    resultado = fluxo.executar(payload, dry_run=args.dry_run)
    print(json.dumps(resultado.as_dict(), ensure_ascii=False, indent=2))
    return 0 if resultado.status_code in (0, 200) else 2


if __name__ == "__main__":
    raise SystemExit(main())
