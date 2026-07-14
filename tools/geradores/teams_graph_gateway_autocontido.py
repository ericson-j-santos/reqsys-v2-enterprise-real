#!/usr/bin/env python3
"""ReqSys Teams Gateway autocontido para Graph e webhook.

Configuração:
- TEAMS_WEBHOOK_URL para notificações automáticas de commits.
- AZURE_TENANT_ID, AZURE_CLIENT_ID e AZURE_CLIENT_SECRET para Graph app-only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any, Mapping

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
TOKEN_SCOPE = "https://graph.microsoft.com/.default"


class GatewayError(RuntimeError):
    pass


@dataclass(frozen=True)
class GatewayConfig:
    tenant_id: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    webhook_url: str | None = None
    timeout_seconds: int = 20
    max_attempts: int = 3

    @classmethod
    def from_env(cls) -> "GatewayConfig":
        return cls(
            tenant_id=os.getenv("AZURE_TENANT_ID"),
            client_id=os.getenv("AZURE_CLIENT_ID"),
            client_secret=os.getenv("AZURE_CLIENT_SECRET"),
            webhook_url=os.getenv("TEAMS_WEBHOOK_URL"),
            timeout_seconds=int(os.getenv("HTTP_TIMEOUT_SECONDS", "20")),
            max_attempts=int(os.getenv("HTTP_MAX_ATTEMPTS", "3")),
        )

    @property
    def graph_configured(self) -> bool:
        return bool(self.tenant_id and self.client_id and self.client_secret)


@dataclass(frozen=True)
class GatewayResult:
    success: bool
    route: str
    correlation_id: str
    status_code: int | None = None
    message_id: str | None = None
    response: Mapping[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "route": self.route,
            "correlation_id": self.correlation_id,
            "status_code": self.status_code,
            "message_id": self.message_id,
            "response": dict(self.response or {}),
        }


class HttpClient:
    def __init__(self, config: GatewayConfig) -> None:
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

    def request(
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

        request_headers = {"Accept": "application/json", **dict(headers or {})}
        body: bytes | None = None
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
                with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                    raw = response.read().decode("utf-8", errors="replace")
                    return int(response.status), self.safe_json(raw)
            except urllib.error.HTTPError as exc:
                raw = exc.read().decode("utf-8", errors="replace")
                if exc.code not in {429, 500, 502, 503, 504} or attempt == self.config.max_attempts:
                    raise GatewayError(f"HTTP {exc.code}: {self.safe_json(raw)}") from exc
                retry_after = int(exc.headers.get("Retry-After", "1"))
                time.sleep(min(retry_after, 5))
                last_error = exc
            except (urllib.error.URLError, TimeoutError) as exc:
                last_error = exc
                if attempt == self.config.max_attempts:
                    break
                time.sleep(min(2 ** (attempt - 1), 4))
        raise GatewayError(f"Falha de comunicação após {self.config.max_attempts} tentativas: {last_error}")


class TeamsGateway:
    def __init__(self, config: GatewayConfig | None = None, http: HttpClient | None = None) -> None:
        self.config = config or GatewayConfig.from_env()
        self.http = http or HttpClient(self.config)

    def status(self) -> dict[str, Any]:
        return {
            "service": "reqsys-teams-gateway",
            "webhook_configured": bool(self.config.webhook_url),
            "graph_configured": self.config.graph_configured,
            "routes": ["webhook", "graph_delegated_chat", "graph_app_channel"],
        }

    def send_webhook(self, message: str, title: str, dry_run: bool = False) -> GatewayResult:
        self._validate_message(message)
        if not self.config.webhook_url:
            raise GatewayError("TEAMS_WEBHOOK_URL não configurado")
        correlation_id = str(uuid.uuid4())
        payload = {
            "to": "Canal ReqSys - Commits",
            "title": title,
            "content": message,
            "signature": "ReqSys",
            "stampDate": datetime.now(timezone.utc).isoformat(),
            "correlationId": correlation_id,
        }
        if dry_run:
            return GatewayResult(True, "webhook", correlation_id, response={"planned": True, "payload": payload})
        status, response = self.http.request(
            "POST",
            self.config.webhook_url,
            headers={"X-Correlation-ID": correlation_id},
            payload=payload,
        )
        return GatewayResult(200 <= status < 300, "webhook", correlation_id, status_code=status, response=response)

    def _app_token(self) -> str:
        if not self.config.graph_configured:
            raise GatewayError("Credenciais Graph não configuradas")
        token_url = f"https://login.microsoftonline.com/{urllib.parse.quote(self.config.tenant_id or '')}/oauth2/v2.0/token"
        _, response = self.http.request(
            "POST",
            token_url,
            form={
                "client_id": self.config.client_id or "",
                "client_secret": self.config.client_secret or "",
                "scope": TOKEN_SCOPE,
                "grant_type": "client_credentials",
            },
        )
        token = response.get("access_token")
        if not isinstance(token, str) or not token:
            raise GatewayError("Microsoft Identity não retornou access_token")
        return token

    def send_channel(self, team_id: str, channel_id: str, message: str, dry_run: bool = False) -> GatewayResult:
        self._validate_id(team_id, "team_id")
        self._validate_id(channel_id, "channel_id")
        self._validate_message(message)
        correlation_id = str(uuid.uuid4())
        if dry_run:
            return GatewayResult(True, "graph_app_channel", correlation_id, response={"planned": True})
        token = self._app_token()
        status, response = self.http.request(
            "POST",
            f"{GRAPH_BASE_URL}/teams/{urllib.parse.quote(team_id, safe='')}/channels/{urllib.parse.quote(channel_id, safe='')}/messages",
            headers={"Authorization": f"Bearer {token}", "client-request-id": correlation_id},
            payload={"body": {"contentType": "text", "content": message}},
        )
        message_id = response.get("id") if isinstance(response.get("id"), str) else None
        return GatewayResult(200 <= status < 300, "graph_app_channel", correlation_id, status, message_id, response)

    def send_chat(self, chat_id: str, message: str, token: str, dry_run: bool = False) -> GatewayResult:
        self._validate_id(chat_id, "chat_id")
        self._validate_message(message)
        if not token.strip():
            raise GatewayError("Token delegado obrigatório")
        correlation_id = str(uuid.uuid4())
        if dry_run:
            return GatewayResult(True, "graph_delegated_chat", correlation_id, response={"planned": True})
        status, response = self.http.request(
            "POST",
            f"{GRAPH_BASE_URL}/chats/{urllib.parse.quote(chat_id, safe='')}/messages",
            headers={"Authorization": f"Bearer {token}", "client-request-id": correlation_id},
            payload={"body": {"contentType": "text", "content": message}},
        )
        message_id = response.get("id") if isinstance(response.get("id"), str) else None
        return GatewayResult(200 <= status < 300, "graph_delegated_chat", correlation_id, status, message_id, response)

    @staticmethod
    def _validate_id(value: str, name: str) -> None:
        if not value.strip() or len(value) > 500:
            raise GatewayError(f"{name} inválido")

    @staticmethod
    def _validate_message(message: str) -> None:
        if not message.strip():
            raise GatewayError("Mensagem obrigatória")
        if len(message) > 28_000:
            raise GatewayError("Mensagem excede 28.000 caracteres")


def self_test() -> dict[str, Any]:
    assert HttpClient.safe_json("1") == {"value": 1}
    assert HttpClient.safe_json("ok") == {"message": "ok"}
    config = GatewayConfig(webhook_url="https://example.invalid/hook")
    result = TeamsGateway(config).send_webhook("teste", "ReqSys", dry_run=True)
    assert result.success and result.route == "webhook"
    try:
        TeamsGateway(config).send_chat("chat", "teste", "")
        raise AssertionError("token vazio deveria falhar")
    except GatewayError:
        pass
    return {"passed": 4, "status": "ok"}


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    sub = root.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("self-test")
    webhook = sub.add_parser("send-webhook")
    webhook.add_argument("--message", required=True)
    webhook.add_argument("--title", default="ReqSys Teams Gateway")
    webhook.add_argument("--dry-run", action="store_true")
    channel = sub.add_parser("send-channel")
    channel.add_argument("--team-id", required=True)
    channel.add_argument("--channel-id", required=True)
    channel.add_argument("--message", required=True)
    channel.add_argument("--dry-run", action="store_true")
    chat = sub.add_parser("send-chat")
    chat.add_argument("--chat-id", required=True)
    chat.add_argument("--message", required=True)
    chat.add_argument("--delegated-token", default=os.getenv("TEAMS_DELEGATED_TOKEN", ""))
    chat.add_argument("--dry-run", action="store_true")
    return root


def main() -> int:
    args = parser().parse_args()
    gateway = TeamsGateway()
    try:
        if args.command == "status":
            result: Any = gateway.status()
        elif args.command == "self-test":
            result = self_test()
        elif args.command == "send-webhook":
            result = gateway.send_webhook(args.message, args.title, args.dry_run).as_dict()
        elif args.command == "send-channel":
            result = gateway.send_channel(args.team_id, args.channel_id, args.message, args.dry_run).as_dict()
        else:
            result = gateway.send_chat(args.chat_id, args.message, args.delegated_token, args.dry_run).as_dict()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (GatewayError, ValueError) as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
