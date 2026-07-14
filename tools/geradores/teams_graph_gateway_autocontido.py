#!/usr/bin/env python3
"""ReqSys Teams Gateway + Microsoft Graph, autocontido e sem dependências externas.

Configuração por ambiente:
  AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET
  TEAMS_WEBHOOK_URL (opcional)

Exemplos:
  python teams_graph_gateway_autocontido.py status
  python teams_graph_gateway_autocontido.py send-chat --chat-id ID --message "Olá" --delegated-token TOKEN
  python teams_graph_gateway_autocontido.py send-channel --team-id ID --channel-id ID --message "Deploy OK"
  python teams_graph_gateway_autocontido.py send-webhook --message "Deploy OK"
  python teams_graph_gateway_autocontido.py self-test
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any, Mapping

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
TOKEN_SCOPE = "https://graph.microsoft.com/.default"
LOG = logging.getLogger("reqsys.teams_graph_gateway")


class GatewayError(RuntimeError):
    """Falha governada do gateway."""


@dataclass(frozen=True)
class GatewayConfig:
    tenant_id: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    webhook_url: str | None = None
    graph_base_url: str = GRAPH_BASE_URL
    timeout_seconds: int = 20
    max_attempts: int = 3
    verify_tls: bool = True

    @classmethod
    def from_env(cls) -> "GatewayConfig":
        return cls(
            tenant_id=os.getenv("AZURE_TENANT_ID"),
            client_id=os.getenv("AZURE_CLIENT_ID"),
            client_secret=os.getenv("AZURE_CLIENT_SECRET"),
            webhook_url=os.getenv("TEAMS_WEBHOOK_URL"),
            graph_base_url=os.getenv("GRAPH_BASE_URL", GRAPH_BASE_URL).rstrip("/"),
            timeout_seconds=int(os.getenv("HTTP_TIMEOUT_SECONDS", "20")),
            max_attempts=int(os.getenv("HTTP_MAX_ATTEMPTS", "3")),
            verify_tls=os.getenv("VERIFY_TLS", "true").lower() not in {"0", "false", "no"},
        )

    @property
    def app_only_configured(self) -> bool:
        return bool(self.tenant_id and self.client_id and self.client_secret)


@dataclass(frozen=True)
class GatewayResult:
    success: bool
    route: str
    correlation_id: str
    status_code: int | None = None
    message_id: str | None = None
    error: str | None = None
    response: Mapping[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "route": self.route,
            "correlation_id": self.correlation_id,
            "status_code": self.status_code,
            "message_id": self.message_id,
            "error": self.error,
            "response": dict(self.response or {}),
        }


class HttpClient:
    def __init__(self, config: GatewayConfig) -> None:
        self.config = config
        self.ssl_context = None if config.verify_tls else ssl._create_unverified_context()

    def request_json(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        payload: Mapping[str, Any] | None = None,
        form: Mapping[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        if payload is not None and form is not None:
            raise ValueError("payload e form são mutuamente exclusivos")
        body: bytes | None = None
        request_headers = {"Accept": "application/json", **dict(headers or {})}
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            request_headers["Content-Type"] = "application/json; charset=utf-8"
        elif form is not None:
            body = urllib.parse.urlencode(form).encode("utf-8")
            request_headers["Content-Type"] = "application/x-www-form-urlencoded"

        last_error: Exception | None = None
        for attempt in range(1, self.config.max_attempts + 1):
            request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
            try:
                with urllib.request.urlopen(
                    request,
                    timeout=self.config.timeout_seconds,
                    context=self.ssl_context,
                ) as response:
                    raw = response.read().decode("utf-8")
                    return int(response.status), json.loads(raw) if raw else {}
            except urllib.error.HTTPError as exc:
                raw = exc.read().decode("utf-8", errors="replace")
                data = self._safe_json(raw)
                if exc.code not in {429, 500, 502, 503, 504} or attempt == self.config.max_attempts:
                    detail = data.get("error", data)
                    raise GatewayError(f"HTTP {exc.code}: {detail}") from exc
                retry_after = int(exc.headers.get("Retry-After", "1"))
                time.sleep(min(retry_after, 5))
                last_error = exc
            except (urllib.error.URLError, TimeoutError) as exc:
                last_error = exc
                if attempt == self.config.max_attempts:
                    break
                time.sleep(min(2 ** (attempt - 1), 4))
        raise GatewayError(f"Falha de comunicação após {self.config.max_attempts} tentativas: {last_error}")

    @staticmethod
    def _safe_json(raw: str) -> dict[str, Any]:
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except json.JSONDecodeError:
            return {"message": raw[:1000]}


class GraphTokenProvider:
    def __init__(self, config: GatewayConfig, http: HttpClient) -> None:
        self.config = config
        self.http = http
        self._token: str | None = None
        self._expires_at = 0.0

    def get_app_token(self) -> str:
        if self._token and time.time() < self._expires_at - 60:
            return self._token
        if not self.config.app_only_configured:
            raise GatewayError("Graph app-only não configurado: informe AZURE_TENANT_ID, AZURE_CLIENT_ID e AZURE_CLIENT_SECRET")
        token_url = f"https://login.microsoftonline.com/{urllib.parse.quote(self.config.tenant_id or '')}/oauth2/v2.0/token"
        _, data = self.http.request_json(
            "POST",
            token_url,
            form={
                "client_id": self.config.client_id or "",
                "client_secret": self.config.client_secret or "",
                "scope": TOKEN_SCOPE,
                "grant_type": "client_credentials",
            },
        )
        token = data.get("access_token")
        if not isinstance(token, str) or not token:
            raise GatewayError("Microsoft Identity não retornou access_token")
        self._token = token
        self._expires_at = time.time() + int(data.get("expires_in", 3600))
        return token


class TeamsGraphGateway:
    def __init__(self, config: GatewayConfig | None = None, http: HttpClient | None = None) -> None:
        self.config = config or GatewayConfig.from_env()
        self.http = http or HttpClient(self.config)
        self.tokens = GraphTokenProvider(self.config, self.http)

    def status(self) -> dict[str, Any]:
        return {
            "service": "reqsys-teams-graph-gateway",
            "schema_version": "1.0.0",
            "graph_base_url": self.config.graph_base_url,
            "app_only_configured": self.config.app_only_configured,
            "webhook_configured": bool(self.config.webhook_url),
            "tls_verification": self.config.verify_tls,
            "routes": ["graph_delegated_chat", "graph_app_channel", "webhook"],
            "security": {"secrets_from_environment": True, "token_logging": False},
        }

    def send_chat(
        self,
        chat_id: str,
        message: str,
        *,
        delegated_token: str,
        content_type: str = "text",
        correlation_id: str | None = None,
        dry_run: bool = False,
    ) -> GatewayResult:
        self._validate_id("chat_id", chat_id)
        self._validate_message(message)
        if not delegated_token.strip():
            raise GatewayError("delegated_token é obrigatório para chat humano")
        return self._send_graph(
            route="graph_delegated_chat",
            path=f"/chats/{urllib.parse.quote(chat_id, safe='')}/messages",
            token=delegated_token,
            message=message,
            content_type=content_type,
            correlation_id=correlation_id,
            dry_run=dry_run,
        )

    def send_channel(
        self,
        team_id: str,
        channel_id: str,
        message: str,
        *,
        content_type: str = "text",
        correlation_id: str | None = None,
        dry_run: bool = False,
    ) -> GatewayResult:
        self._validate_id("team_id", team_id)
        self._validate_id("channel_id", channel_id)
        self._validate_message(message)
        token = "dry-run-token" if dry_run else self.tokens.get_app_token()
        return self._send_graph(
            route="graph_app_channel",
            path=f"/teams/{urllib.parse.quote(team_id, safe='')}/channels/{urllib.parse.quote(channel_id, safe='')}/messages",
            token=token,
            message=message,
            content_type=content_type,
            correlation_id=correlation_id,
            dry_run=dry_run,
        )

    def send_webhook(
        self,
        message: str,
        *,
        webhook_url: str | None = None,
        title: str = "ReqSys Teams Gateway",
        correlation_id: str | None = None,
        dry_run: bool = False,
    ) -> GatewayResult:
        self._validate_message(message)
        url = webhook_url or self.config.webhook_url
        if not url:
            raise GatewayError("Webhook não configurado: informe --webhook-url ou TEAMS_WEBHOOK_URL")
        correlation_id = correlation_id or str(uuid.uuid4())
        payload = {
            "type": "message",
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "https://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {"type": "TextBlock", "weight": "Bolder", "size": "Medium", "text": title},
                        {"type": "TextBlock", "wrap": True, "text": message},
                        {"type": "TextBlock", "isSubtle": True, "spacing": "Small", "text": f"Correlation ID: {correlation_id}"},
                    ],
                },
            }],
        }
        if dry_run:
            return GatewayResult(True, "webhook", correlation_id, response={"planned": True, "payload": payload})
        status, response = self.http.request_json("POST", url, headers={"X-Correlation-ID": correlation_id}, payload=payload)
        return GatewayResult(status < 300, "webhook", correlation_id, status_code=status, response=response)

    def _send_graph(
        self,
        *,
        route: str,
        path: str,
        token: str,
        message: str,
        content_type: str,
        correlation_id: str | None,
        dry_run: bool,
    ) -> GatewayResult:
        if content_type not in {"text", "html"}:
            raise GatewayError("content_type deve ser text ou html")
        correlation_id = correlation_id or str(uuid.uuid4())
        payload = {"body": {"contentType": content_type, "content": message}}
        if dry_run:
            return GatewayResult(True, route, correlation_id, response={"planned": True, "path": path, "payload": payload})
        status, response = self.http.request_json(
            "POST",
            f"{self.config.graph_base_url}{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Correlation-ID": correlation_id,
                "client-request-id": correlation_id,
                "return-client-request-id": "true",
            },
            payload=payload,
        )
        message_id = response.get("id") if isinstance(response.get("id"), str) else None
        return GatewayResult(status < 300, route, correlation_id, status_code=status, message_id=message_id, response=response)

    @staticmethod
    def _validate_id(name: str, value: str) -> None:
        if not value or not value.strip() or len(value) > 500:
            raise GatewayError(f"{name} inválido")

    @staticmethod
    def _validate_message(message: str) -> None:
        if not message or not message.strip():
            raise GatewayError("message é obrigatória")
        if len(message) > 28_000:
            raise GatewayError("message excede o limite governado de 28.000 caracteres")


class FakeHttpClient:
    """Cliente somente para self-test; não realiza rede."""
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def request_json(self, method: str, url: str, **kwargs: Any) -> tuple[int, dict[str, Any]]:
        self.calls.append({"method": method, "url": url, **kwargs})
        if url.endswith("/token"):
            return 200, {"access_token": "fake-token", "expires_in": 3600}
        return 201, {"id": "message-123"}


def run_self_test() -> dict[str, Any]:
    fake = FakeHttpClient()
    config = GatewayConfig(tenant_id="tenant", client_id="client", client_secret="secret", webhook_url="https://example.invalid/hook")
    gateway = TeamsGraphGateway(config=config, http=fake)
    gateway.tokens = GraphTokenProvider(config, fake)

    chat = gateway.send_chat("chat-1", "Olá", delegated_token="delegated", dry_run=True)
    assert chat.success and chat.route == "graph_delegated_chat" and chat.response and chat.response["planned"]

    channel = gateway.send_channel("team-1", "channel-1", "Deploy concluído")
    assert channel.success and channel.message_id == "message-123"
    assert any(call["url"].endswith("/token") for call in fake.calls)
    assert any("/teams/team-1/channels/channel-1/messages" in call["url"] for call in fake.calls)

    webhook = gateway.send_webhook("Status OK", dry_run=True)
    assert webhook.success and webhook.route == "webhook"

    try:
        gateway.send_chat("chat-1", "Olá", delegated_token="")
        raise AssertionError("token delegado vazio deveria falhar")
    except GatewayError:
        pass

    try:
        gateway.send_channel("", "channel-1", "x", dry_run=True)
        raise AssertionError("team_id vazio deveria falhar")
    except GatewayError:
        pass

    return {"passed": 5, "network_calls": len(fake.calls), "status": "ok"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ReqSys Teams Gateway + Microsoft Graph autocontido")
    parser.add_argument("--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("self-test")

    chat = sub.add_parser("send-chat")
    chat.add_argument("--chat-id", required=True)
    chat.add_argument("--message", required=True)
    chat.add_argument("--delegated-token", default=os.getenv("TEAMS_DELEGATED_TOKEN"))
    chat.add_argument("--content-type", choices=["text", "html"], default="text")
    chat.add_argument("--dry-run", action="store_true")

    channel = sub.add_parser("send-channel")
    channel.add_argument("--team-id", required=True)
    channel.add_argument("--channel-id", required=True)
    channel.add_argument("--message", required=True)
    channel.add_argument("--content-type", choices=["text", "html"], default="text")
    channel.add_argument("--dry-run", action="store_true")

    webhook = sub.add_parser("send-webhook")
    webhook.add_argument("--message", required=True)
    webhook.add_argument("--title", default="ReqSys Teams Gateway")
    webhook.add_argument("--webhook-url")
    webhook.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    gateway = TeamsGraphGateway()
    try:
        if args.command == "status":
            output = gateway.status()
        elif args.command == "self-test":
            output = run_self_test()
        elif args.command == "send-chat":
            output = gateway.send_chat(args.chat_id, args.message, delegated_token=args.delegated_token or "", content_type=args.content_type, dry_run=args.dry_run).as_dict()
        elif args.command == "send-channel":
            output = gateway.send_channel(args.team_id, args.channel_id, args.message, content_type=args.content_type, dry_run=args.dry_run).as_dict()
        else:
            output = gateway.send_webhook(args.message, webhook_url=args.webhook_url, title=args.title, dry_run=args.dry_run).as_dict()
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except (GatewayError, ValueError) as exc:
        LOG.error("Falha governada: %s", exc)
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
