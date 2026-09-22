#!/usr/bin/env python3
"""Gera dois projetos Python autocontidos extraídos do ReqSys.

Origem funcional:
- backend/app/services/email_mime_report_service.py
- backend/app/services/email_report_template.py
- backend/app/services/teams_gateway.py
- backend/app/schemas/teams_gateway.py

Uso:
    python tools/geradores/gerar_servicos_email_teams.py --force --run-tests
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

EMAIL = r'''
from __future__ import annotations
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr
from html import escape
from typing import Iterable

COLORS = {"SUCCESS":"#10b981","INFO":"#3b82f6","WARNING":"#f59e0b","FAILURE":"#ef4444","CRITICAL":"#dc2626"}

@dataclass(frozen=True)
class EmailIdentity:
    email: str
    name: str | None = None
    def __post_init__(self):
        if "@" not in self.email.strip():
            raise ValueError("email invalido")
        object.__setattr__(self, "email", self.email.strip())
        object.__setattr__(self, "name", self.name.strip() if self.name else None)
    def as_header(self) -> str:
        return formataddr((self.name, self.email)) if self.name else self.email

@dataclass(frozen=True)
class StatusCard:
    label: str
    value: str
    status: str
    description: str = ""

@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    username: str | None = None
    password: str | None = None
    use_tls: bool = True
    use_ssl: bool = False
    timeout: int = 30
    def __post_init__(self):
        if not self.host.strip() or self.port <= 0:
            raise ValueError("configuracao SMTP invalida")
        if self.use_tls and self.use_ssl:
            raise ValueError("use_tls e use_ssl sao mutuamente exclusivos")

def _status(status: str) -> str:
    value = status.strip().upper()
    return value if value in COLORS else "INFO"

def render_html(title: str, subtitle: str, correlation_id: str, cards: Iterable[StatusCard]) -> str:
    cards_html = []
    for card in cards:
        color = COLORS[_status(card.status)]
        cards_html.append(f'<td style="padding:8px"><div style="border-left:6px solid {color};background:#fff;padding:12px"><b>{escape(card.label)}</b><div style="font-size:22px">{escape(card.value)}</div><small>{escape(card.description)}</small></div></td>')
    return f'<!doctype html><html lang="pt-BR"><body style="font-family:Arial;background:#f4f6f9"><table role="presentation" style="width:100%"><tr><td align="center"><table role="presentation" style="max-width:900px;width:100%;background:#fff"><tr><td style="background:#0f172a;color:#fff;padding:24px"><h1>{escape(title)}</h1><p>{escape(subtitle)}</p></td></tr><tr><td style="padding:20px"><table role="presentation" style="width:100%"><tr>{"".join(cards_html)}</tr></table><p><b>Correlation ID:</b> {escape(correlation_id)}</p></td></tr></table></td></tr></table></body></html>'

def render_text(title: str, subtitle: str, correlation_id: str, cards: Iterable[StatusCard]) -> str:
    linhas = [title, subtitle, "", "STATUS", "------"]
    for c in cards:
        linhas.append(f"[{_status(c.status)}] {c.label}: {c.value} - {c.description}")
    linhas.append(f"Correlation ID: {correlation_id}")
    return "\n".join(linhas)

def build_message(*, sender: EmailIdentity, recipients: Iterable[EmailIdentity], subject: str, title: str, subtitle: str, correlation_id: str, cards: Iterable[StatusCard]) -> EmailMessage:
    destinatarios = list(recipients)
    if not destinatarios:
        raise ValueError("ao menos um destinatario e obrigatorio")
    cards = list(cards)
    msg = EmailMessage()
    msg["From"] = sender.as_header()
    msg["To"] = ", ".join(r.as_header() for r in destinatarios)
    msg["Subject"] = subject.strip()
    msg["X-Correlation-ID"] = correlation_id
    msg["X-ReqSys-Report-Type"] = "executive-runtime-governance"
    msg.set_content(render_text(title, subtitle, correlation_id, cards), subtype="plain", charset="utf-8")
    msg.add_alternative(render_html(title, subtitle, correlation_id, cards), subtype="html", charset="utf-8")
    return msg

def send_smtp(config: SmtpConfig, message: EmailMessage, correlation_id: str, dry_run: bool = False) -> dict:
    recipients = [x.strip() for x in message.get("To", "").split(",") if x.strip()]
    if dry_run:
        return {"sent": False, "dry_run": True, "correlation_id": correlation_id, "recipients": recipients, "provider_response": {"planned": True}}
    try:
        smtp_cls = smtplib.SMTP_SSL if config.use_ssl else smtplib.SMTP
        with smtp_cls(config.host, config.port, timeout=config.timeout) as smtp:
            if config.use_tls:
                smtp.starttls()
            if config.username:
                smtp.login(config.username, config.password or "")
            smtp.send_message(message)
        return {"sent": True, "dry_run": False, "correlation_id": correlation_id, "recipients": recipients, "provider_response": {"smtp_host": config.host, "smtp_port": config.port}}
    except Exception as exc:
        return {"sent": False, "dry_run": False, "correlation_id": correlation_id, "recipients": recipients, "error": str(exc)}
'''.lstrip()

EMAIL_TEST = r'''
import unittest
from service import EmailIdentity, StatusCard, SmtpConfig, build_message, render_html, send_smtp

class EmailServiceTest(unittest.TestCase):
    def test_html_escapa_conteudo(self):
        html = render_html("Rel <script>", "Sub", "corr-1", [StatusCard("CI", "OK", "SUCCESS", "<x>")])
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&lt;x&gt;", html)
        self.assertIn("corr-1", html)
    def test_mime_tem_headers_governanca(self):
        msg = build_message(sender=EmailIdentity("noreply@example.com", "ReqSys"), recipients=[EmailIdentity("ops@example.com", "Ops")], subject="Relatorio", title="T", subtitle="S", correlation_id="corr-2", cards=[])
        self.assertTrue(msg.is_multipart())
        self.assertEqual(msg["X-Correlation-ID"], "corr-2")
        self.assertEqual(msg["X-ReqSys-Report-Type"], "executive-runtime-governance")
    def test_dry_run_nao_envia(self):
        msg = build_message(sender=EmailIdentity("noreply@example.com"), recipients=[EmailIdentity("ops@example.com")], subject="Relatorio", title="T", subtitle="S", correlation_id="corr-3", cards=[])
        result = send_smtp(SmtpConfig("smtp.example.invalid", 587), msg, "corr-3", dry_run=True)
        self.assertFalse(result["sent"])
        self.assertTrue(result["dry_run"])
        self.assertTrue(result["provider_response"]["planned"])
if __name__ == "__main__": unittest.main()
'''.lstrip()

TEAMS = r'''
from __future__ import annotations
import asyncio, json, urllib.error, urllib.request, uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

@dataclass(frozen=True)
class GatewayConfig:
    webhook_url: str | None = None
    azure_configured: bool = False
    graph_app_configured: bool = False

@dataclass(frozen=True)
class MessageRequest:
    texto: str
    destino_tipo: str = "auto"
    modo: str = "auto"
    destino_id: str | None = None
    content_type: str = "text"
    usuario_access_token: str | None = None
    webhook_url: str | None = None
    usuario_a_aad_object_id: str | None = None
    usuario_b_aad_object_id: str | None = None
    permitir_fallback: bool = True
    dry_run: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    def __post_init__(self):
        if not self.texto.strip():
            raise ValueError("texto e obrigatorio")
        if self.destino_tipo not in {"auto","chat","chat_1a1","canal","webhook"}:
            raise ValueError("destino_tipo invalido")
        if self.modo not in {"auto","graph_delegado","webhook","graph_app_only","bot"}:
            raise ValueError("modo invalido")
        object.__setattr__(self, "texto", self.texto.strip())

@dataclass(frozen=True)
class ProviderResult:
    enviado: bool
    status_code: int | None = None
    message_id: str | None = None
    chat_id: str | None = None
    erro: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

class WebhookProvider(Protocol):
    def enviar(self, url: str, request: MessageRequest, correlation_id: str) -> ProviderResult: ...
class AsyncProvider(Protocol):
    async def enviar(self, request: MessageRequest, correlation_id: str) -> ProviderResult: ...

def webhook_payload(texto: str, content_type: str, metadata: dict[str, Any]) -> dict:
    titulo = metadata.get("titulo") or metadata.get("title") or "ReqSys Teams Gateway"
    conteudo = texto if content_type == "text" else texto.replace("<br>", "\n")
    return {"type":"message","attachments":[{"contentType":"application/vnd.microsoft.card.adaptive","content":{"$schema":"http://adaptivecards.io/schemas/adaptive-card.json","type":"AdaptiveCard","version":"1.2","body":[{"type":"TextBlock","size":"Medium","weight":"Bolder","text":titulo},{"type":"TextBlock","text":conteudo,"wrap":True}]}}]}

class UrlLibWebhookProvider:
    def enviar(self, url: str, request: MessageRequest, correlation_id: str) -> ProviderResult:
        data = json.dumps(webhook_payload(request.texto, request.content_type, request.metadata)).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json","X-Correlation-ID":correlation_id}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:  # nosec B310: URL governada por configuracao
                return ProviderResult(True, status_code=int(getattr(resp, "status", 200)))
        except urllib.error.HTTPError as exc:
            return ProviderResult(False, status_code=exc.code, erro=f"HTTP {exc.code}")
        except Exception as exc:
            return ProviderResult(False, erro=str(exc))

class NullAsyncProvider:
    async def enviar(self, request: MessageRequest, correlation_id: str) -> ProviderResult:
        return ProviderResult(False, erro="provider Graph nao configurado; injete um adapter real")

class TeamsGateway:
    def __init__(self, config: GatewayConfig | None = None, webhook_provider: WebhookProvider | None = None, delegated_provider: AsyncProvider | None = None, app_provider: AsyncProvider | None = None):
        self.config = config or GatewayConfig()
        self.webhook_provider = webhook_provider or UrlLibWebhookProvider()
        self.delegated_provider = delegated_provider or NullAsyncProvider()
        self.app_provider = app_provider or NullAsyncProvider()
    def status_gateway(self) -> dict:
        return {"schema_version":"1.0.0","status":"operacional" if any([self.config.webhook_url,self.config.azure_configured,self.config.graph_app_configured]) else "pendente_configuracao","rotas":[{"canal":"graph_delegado","disponivel":self.config.azure_configured,"requer_usuario_logado":True},{"canal":"webhook","disponivel":bool(self.config.webhook_url),"requer_usuario_logado":False},{"canal":"graph_app_only","disponivel":self.config.graph_app_configured,"requer_usuario_logado":False}],"politica":{"chat_humano_sem_usuario_logado":"bloquear_com_mensagem_explicita","fallback":"webhook quando permitido e configurado"}}
    def selecionar_rota(self, req: MessageRequest) -> dict:
        if req.modo == "graph_delegado" or (req.modo == "auto" and req.destino_tipo in ("auto","chat","chat_1a1") and req.usuario_access_token): return {"canal":"graph_delegado"}
        if req.modo == "webhook" or (req.modo == "auto" and (req.destino_tipo in ("canal","webhook") or (req.destino_tipo == "auto" and (req.webhook_url or self.config.webhook_url)))): return {"canal":"webhook"}
        if req.modo == "graph_app_only": return {"canal":"graph_app_only"}
        return {"canal":None}
    async def enviar(self, req: MessageRequest, correlation_id: str | None = None) -> dict:
        corr = correlation_id or str(uuid.uuid4())
        canal = self.selecionar_rota(req)["canal"]
        if req.dry_run: return self._result(req, corr, False, canal, motivo="dry_run: mensagem nao enviada", provider={"planned": True})
        if canal == "graph_delegado":
            if not req.usuario_access_token: return self._result(req, corr, False, canal, erro="usuario_access_token e obrigatorio")
            if req.destino_tipo != "chat_1a1" and not req.destino_id: return self._result(req, corr, False, canal, erro="destino_id/chat_id e obrigatorio")
            out = await self.delegated_provider.enviar(req, corr)
            if out.enviado or not req.permitir_fallback or not (req.webhook_url or self.config.webhook_url): return self._from(req, corr, canal, out)
            return await self._webhook(req, corr, fallback=True)
        if canal == "webhook": return await self._webhook(req, corr)
        if canal == "graph_app_only": return self._from(req, corr, canal, await self.app_provider.enviar(req, corr))
        return self._result(req, corr, False, None, erro="Chat humano no Teams exige usuario_access_token delegado. Para automacao sem usuario logado, configure webhook ou bot.", motivo="sem_rota_segura")
    async def _webhook(self, req, corr, fallback=False):
        url = req.webhook_url or self.config.webhook_url
        if not url: return self._result(req, corr, False, "webhook", fallback=fallback, erro="Webhook Teams nao configurado")
        return self._from(req, corr, "webhook", await asyncio.to_thread(self.webhook_provider.enviar, url, req, corr), fallback)
    def _from(self, req, corr, canal, out, fallback=False):
        return self._result(req, corr, out.enviado, canal, fallback=fallback, erro=out.erro, provider={"status_code":out.status_code,"message_id":out.message_id,"chat_id":out.chat_id, **out.raw})
    def _result(self, req, corr, entregue, canal, fallback=False, erro=None, motivo=None, provider=None):
        safe = {k:v for k,v in (provider or {}).items() if v is not None and not any(x in k.lower() for x in ("token","secret","password"))}
        return {"entregue":entregue,"canal_usado":canal,"destino_tipo":req.destino_tipo,"correlation_id":corr,"dry_run":req.dry_run,"fallback_usado":fallback,"message_id":safe.get("message_id"),"chat_id":safe.get("chat_id") or req.destino_id,"status_code":safe.get("status_code"),"erro":erro,"motivo":motivo,"provider_response":safe}
'''.lstrip()

TEAMS_TEST = r'''
import asyncio, unittest
from service import MessageRequest, ProviderResult, TeamsGateway, webhook_payload
class FakeAsync:
    def __init__(self, out): self.out, self.calls = out, 0
    async def enviar(self, req, corr): self.calls += 1; return self.out
class FakeWebhook:
    def __init__(self, out): self.out, self.calls = out, 0
    def enviar(self, url, req, corr): self.calls += 1; return self.out
class TeamsGatewayTest(unittest.TestCase):
    def run_async(self, coro): return asyncio.run(coro)
    def test_rota_delegada_com_token(self):
        assert TeamsGateway().selecionar_rota(MessageRequest("oi", destino_tipo="chat", destino_id="c", usuario_access_token="t"))["canal"] == "graph_delegado"
    def test_dry_run_nao_chama_provider(self):
        hook = FakeWebhook(ProviderResult(True, status_code=200))
        out = self.run_async(TeamsGateway(webhook_provider=hook).enviar(MessageRequest("x", modo="webhook", webhook_url="https://example.invalid", dry_run=True), "corr"))
        self.assertFalse(out["entregue"]); self.assertEqual(hook.calls, 0); self.assertEqual(out["motivo"], "dry_run: mensagem nao enviada")
    def test_fallback_para_webhook(self):
        delegated = FakeAsync(ProviderResult(False, erro="403")); hook = FakeWebhook(ProviderResult(True, status_code=202))
        out = self.run_async(TeamsGateway(webhook_provider=hook, delegated_provider=delegated).enviar(MessageRequest("x", destino_tipo="chat", destino_id="c", usuario_access_token="t", webhook_url="https://example.invalid"), "corr"))
        self.assertTrue(out["entregue"]); self.assertTrue(out["fallback_usado"]); self.assertEqual(out["canal_usado"], "webhook")
    def test_sanitiza_token(self):
        delegated = FakeAsync(ProviderResult(True, message_id="m", raw={"access_token":"x"}))
        out = self.run_async(TeamsGateway(delegated_provider=delegated).enviar(MessageRequest("x", destino_tipo="chat", destino_id="c", usuario_access_token="t"), "corr"))
        self.assertNotIn("access_token", out["provider_response"]); self.assertEqual(out["message_id"], "m")
    def test_payload_adaptive_card(self):
        payload = webhook_payload("A<br>B", "html", {"titulo":"T"})
        self.assertEqual(payload["attachments"][0]["contentType"], "application/vnd.microsoft.card.adaptive")
        self.assertIn("A\nB", payload["attachments"][0]["content"]["body"][1]["text"])
if __name__ == "__main__": unittest.main()
'''.lstrip()

FILES = {
    "email-report-service/README.md": "# Email Report Service\n\nServiço autocontido de e-mail de relatório extraído do ReqSys.\n",
    "email-report-service/pyproject.toml": "[project]\nname='email-report-service'\nversion='1.0.0'\nrequires-python='>=3.11'\n",
    "email-report-service/src/service.py": EMAIL,
    "email-report-service/tests/test_service.py": EMAIL_TEST,
    "teams-gateway-service/README.md": "# Teams Gateway Service\n\nServiço autocontido de gateway Teams extraído do ReqSys.\n",
    "teams-gateway-service/pyproject.toml": "[project]\nname='teams-gateway-service'\nversion='1.0.0'\nrequires-python='>=3.11'\n",
    "teams-gateway-service/src/service.py": TEAMS,
    "teams-gateway-service/tests/test_service.py": TEAMS_TEST,
    "VALIDATION.md": "# Validação\n\nGerador validado localmente com 3 testes do serviço de e-mail e 5 testes do gateway Teams.\n",
}

def gerar(output: Path, force: bool) -> list[Path]:
    criados = []
    for nome, conteudo in FILES.items():
        destino = output / nome
        if destino.exists() and not force:
            raise FileExistsError(f"Arquivo já existe: {destino}. Use --force.")
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(conteudo, encoding="utf-8", newline="\n")
        criados.append(destino)
    return criados

def testar(output: Path) -> None:
    for projeto in ("email-report-service", "teams-gateway-service"):
        raiz = output / projeto
        env = os.environ.copy(); env["PYTHONPATH"] = str(raiz / "src")
        subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(raiz / "tests")], cwd=raiz, env=env, check=True)

def main() -> int:
    parser = argparse.ArgumentParser(description="Gera dois projetos autocontidos: e-mail de relatório e gateway Teams.")
    parser.add_argument("--output", default="artifacts/standalone-services")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--run-tests", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    output = Path(args.output).resolve()
    if args.dry_run:
        print(f"PRECHECK OK: {len(FILES)} arquivos seriam gerados em {output}")
        return 0
    criados = gerar(output, args.force)
    print(f"Gerados {len(criados)} arquivos em {output}")
    if args.run_tests:
        testar(output)
        print("TESTES OK: email-report-service e teams-gateway-service")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
