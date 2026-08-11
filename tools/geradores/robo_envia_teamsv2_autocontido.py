#!/usr/bin/env python3
"""ReqSys robo_envia_teamsv2 autocontido -- cliente fiel do flow real do Power Automate.

`robo_envia_teamsv2` (ambiente "ReqSys Dev", workflow_id=df4fa822-0c89-f111-8076-6045bd3ac4b4)
é um clone "Save As" de `robo_envia_teamsv1` com UMA única mudança: a ação final trocou de
`Postar_mensagem_em_um_chat_ou_canal__` (PostMessageToConversation) para
`Postar_cartão_em_um_chat_ou_canal` (PostCardToConversation) -- mesmo conector `shared_teams`,
poster="Flow bot", location="Chat with Flow bot" (entrega 1:1, não em canal). O flow monta o
Adaptive Card internamente a partir dos campos brutos; este módulo NÃO reimplementa esse
Adaptive Card (não é portável/verificável fora do Maker Portal -- ver
scripts/update_teams_v2_adaptive_card.py para editar o card em si).

Diferença importante em relação a `robo_envia_teamsv1_autocontido.py`: lá, TEAMS_FLOW_BOT_TRIGGER_URL
aponta para um flow auxiliar usado só para o passo do conector (indireção necessária por causa de
uma limitação de design daquele fluxo). Aqui, TEAMS_FLOW_BOT_V2_TRIGGER_URL é a Trigger URL do
PRÓPRIO `robo_envia_teamsv2` -- POST direto nela já dispara o flow inteiro (parse -> valida ->
compose stampDate/correlationId -> monta e posta o Adaptive Card). Contrato de payload
`{to, title, content, signature, correlationId}` confirmado ao vivo (HTTP 200, entrega 1:1
real) em sessão anterior -- não é suposição.

As funções puras abaixo (`analisar_json`, `condicao`, `compose_stamp_date`, ...) replicam a
validação local do flow só para falhar rápido (400) sem gastar uma chamada de rede -- a
composição final do Adaptive Card continua sendo feita pelo flow publicado, nunca localmente.
`--dry-run` nunca produz o mesmo formato de uma entrega real confirmada.

Configuração:
- TEAMS_FLOW_BOT_V2_TRIGGER_URL: Trigger URL real do flow `robo_envia_teamsv2`. Trate como
  segredo (é uma URL assinada/SAS) -- nunca commitar, logar ou colar em texto plano.
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

FUSO_HORARIO = ZoneInfo("America/Sao_Paulo")
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
            trigger_url=os.getenv("TEAMS_FLOW_BOT_V2_TRIGGER_URL"),
            timeout_seconds=int(os.getenv("HTTP_TIMEOUT_SECONDS", "15")),
            max_attempts=int(os.getenv("HTTP_MAX_ATTEMPTS", "3")),
        )

    @property
    def configurado(self) -> bool:
        return bool(self.trigger_url)


class HttpClient:
    """Cliente HTTP com retry -- mesma política de robo_envia_teamsv1_autocontido.py."""

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
    texto = momento.astimezone(FUSO_HORARIO).strftime("%Y-%m-%dT%H:%M:%S%z")
    return f"{texto[:-2]}:{texto[-2:]}"


def _agora_formatado() -> str:
    return _formatar_stamp(datetime.now(tz=ZoneInfo("UTC")))


def analisar_json(corpo: Mapping[str, Any]) -> dict[str, Any]:
    """Pré-validação local -- espelha 'Analisar_JSON' (ParseJson) do flow real."""
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
    return str(uuid.uuid4())


def compose_correlation_id_final(dados: Mapping[str, Any], correlation_id_gerado: str) -> str:
    recebido = dados.get("correlationId")
    return recebido if recebido else correlation_id_gerado


def condicao(dados: Mapping[str, Any]) -> bool:
    """Mesma expressão do 'Condição_' (If) da v1 -- v2 é clone, sem mudança de validação."""
    to = dados.get("to") or ""
    content = dados.get("content") or ""
    title = dados.get("title") or ""
    return "@" in to and len(content) > 0 and len(title) > 0


def compose_stamp_date(dados: Mapping[str, Any]) -> str:
    return dados.get("stampDate") or _agora_formatado()


def montar_payload_trigger(dados: Mapping[str, Any], stamp_date: str, correlation_id_final: str) -> dict[str, Any]:
    """Payload que de fato vai no POST para a Trigger URL -- confirmado ao vivo, sem envelope
    de card e sem poster/location (isso é interno ao flow, não ao chamador)."""
    return {
        "to": (dados.get("to") or "").strip().lower(),
        "title": dados.get("title"),
        "content": dados.get("content"),
        "signature": dados.get("signature"),
        "stampDate": stamp_date,
        "correlationId": correlation_id_final,
    }


def resposta_sucesso(dados: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "to": dados.get("to"),
        "titleLength": len(dados.get("title") or ""),
        "contentLength": len(dados.get("content") or ""),
        "stamp": _agora_formatado(),
    }


def resposta_payload_invalido(dados: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ok": False,
        "error": "Payload inválido",
        "to": dados.get("to"),
        "titleLength": len(dados.get("title") or ""),
        "contentLength": len(dados.get("content") or ""),
        "stamp": _agora_formatado(),
    }


def resposta_falha_interna(correlation_id: str, detalhe: str | None = None) -> dict[str, Any]:
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


class RoboEnviaTeamsV2:
    def __init__(self, config: FluxoConfig | None = None, http: HttpClient | None = None) -> None:
        self.config = config or FluxoConfig.from_env()
        self.http = http or HttpClient(self.config)

    def status(self) -> dict[str, Any]:
        return {
            "service": "robo-envia-teamsv2-autocontido",
            "trigger_configurado": self.config.configurado,
            "workflowid_dev": "df4fa822-0c89-f111-8076-6045bd3ac4b4",
            "acao_final": "Postar_cartão_em_um_chat_ou_canal (PostCardToConversation)",
        }

    def postar_cartao_teams(self, payload_trigger: Mapping[str, Any]) -> tuple[int, dict[str, Any]]:
        """POST direto na Trigger URL do próprio robo_envia_teamsv2 -- dispara o flow inteiro
        (composição do Adaptive Card + entrega 1:1 são feitas pelo Power Automate)."""
        if not self.config.configurado:
            raise FluxoError(
                "TEAMS_FLOW_BOT_V2_TRIGGER_URL não configurada -- necessária para disparar de "
                "verdade o flow `robo_envia_teamsv2` publicado"
            )
        return self.http.post(self.config.trigger_url, payload_trigger)  # type: ignore[arg-type]

    def executar(self, payload: Mapping[str, Any], dry_run: bool = False) -> ResultadoFluxo:
        correlation_id_gerado = compose_correlation_id()
        try:
            dados = analisar_json(payload)
            correlation_id_final = compose_correlation_id_final(dados, correlation_id_gerado)

            if not condicao(dados):
                return ResultadoFluxo(400, resposta_payload_invalido(dados), enviado=False)

            stamp_date = compose_stamp_date(dados)
            payload_trigger = montar_payload_trigger(dados, stamp_date, correlation_id_final)

            if dry_run:
                return ResultadoFluxo(
                    0,
                    {"planned": True, "payload_trigger": payload_trigger, "correlationId": correlation_id_final},
                    enviado=False,
                )

            status_code, resposta_http = self.postar_cartao_teams(payload_trigger)
            if not (200 <= status_code < 300):
                detalhe = f"HTTP {status_code} do flow publicado: {resposta_http}"
                return ResultadoFluxo(500, resposta_falha_interna(correlation_id_gerado, detalhe), enviado=False)

            return ResultadoFluxo(200, resposta_sucesso(dados), enviado=True)

        except FluxoError as exc:
            return ResultadoFluxo(500, resposta_falha_interna(correlation_id_gerado, str(exc)), enviado=False)


def self_test() -> dict[str, Any]:
    """Bateria mínima executável sem rede -- espelha o self-test de robo_envia_teamsv1_autocontido.py."""
    fluxo = RoboEnviaTeamsV2(FluxoConfig())
    base = {"to": "fulano@tieri659.onmicrosoft.com", "title": "Aviso", "content": "corpo", "signature": "ReqSys"}

    planejado = fluxo.executar(base, dry_run=True)
    assert planejado.enviado is False and planejado.body.get("planned") is True

    invalido = fluxo.executar({**base, "to": "sem-arroba"}, dry_run=True)
    assert invalido.status_code == 400 and invalido.enviado is False

    faltando = fluxo.executar({"to": base["to"], "title": "Aviso"}, dry_run=False)
    assert faltando.status_code == 500 and faltando.enviado is False

    sem_config = fluxo.executar(base, dry_run=False)
    assert sem_config.status_code == 500 and sem_config.enviado is False
    assert "TEAMS_FLOW_BOT_V2_TRIGGER_URL" in sem_config.body["detalhe"]

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
    fluxo = RoboEnviaTeamsV2()
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
