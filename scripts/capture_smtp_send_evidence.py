#!/usr/bin/env python3
"""Captura evidência real de envio SMTP do pipeline Prospecção Movimento.

Objetivo: provar que o mecanismo de envio (composição MIME em
`email_service.build_email_movimento_message` + `SmtpEmailSender`, ambos
código de produção) sai de fato pela rede via protocolo SMTP real — e não
apenas em um `dry_run` ou em um teste unitário com `smtplib` mockado.

Isso NÃO substitui a validação do P0 contra o SMTP corporativo real (que
depende de `MOVIMENTO_EMAIL_SMTP_*` reais, ainda pendentes — ver
`artifacts/p0-external-blocker-handoff.md`). É evidência de que o mecanismo
de envio está íntegro, usando dados sintéticos, contra um receptor SMTP real
(sobe um servidor SMTP mínimo em texto puro localmente, equivalente em
protocolo ao MailHog já cabeado em `docker-compose.yml`, sem depender de
Docker estar disponível no ambiente).

Uso:
    python scripts/capture_smtp_send_evidence.py
"""
from __future__ import annotations

import json
import socket
import sys
import threading
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

ARTIFACT_DIR = ROOT / "artifacts" / "real-evidence-local"
HOST = "127.0.0.1"
PORT = 1025


class _CapturingSMTPServer:
    """Servidor SMTP mínimo (RFC 5321: EHLO/MAIL/RCPT/DATA/QUIT), sem
    STARTTLS/AUTH — suficiente para `MOVIMENTO_EMAIL_SMTP_USE_TLS=false` sem
    usuário, equivalente em protocolo ao MailHog já cabeado no
    `docker-compose.yml`. Sem dependências externas (smtpd/asyncore foram
    removidos do stdlib no Python 3.12)."""

    def __init__(self, host: str, port: int) -> None:
        self.captured: list[dict[str, object]] = []
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((host, port))
        self._sock.listen(1)
        self._sock.settimeout(0.5)

    def close(self) -> None:
        self._sock.close()

    def serve_one(self, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            try:
                conn, addr = self._sock.accept()
            except socket.timeout:
                continue
            with conn:
                self._handle_connection(conn, addr)
            return

    def _handle_connection(self, conn: socket.socket, addr: tuple[str, int]) -> None:
        conn.settimeout(10)
        rfile = conn.makefile("rb")
        mail_from = ""
        rcpt_tos: list[str] = []
        conn.sendall(b"220 localhost ReqSys evidence SMTP ready\r\n")
        while True:
            line = rfile.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="ignore").strip()
            upper = text.upper()
            if upper.startswith(("EHLO", "HELO")):
                conn.sendall(b"250 localhost\r\n")
            elif upper.startswith("MAIL FROM"):
                mail_from = text.split(":", 1)[1].strip()
                conn.sendall(b"250 OK\r\n")
            elif upper.startswith("RCPT TO"):
                rcpt_tos.append(text.split(":", 1)[1].strip())
                conn.sendall(b"250 OK\r\n")
            elif upper.startswith("DATA"):
                conn.sendall(b"354 End data with <CR><LF>.<CR><LF>\r\n")
                raw_lines: list[bytes] = []
                while True:
                    data_line = rfile.readline()
                    if not data_line or data_line == b".\r\n":
                        break
                    raw_lines.append(data_line)
                raw = b"".join(raw_lines)
                self.captured.append(
                    {
                        "peer": f"{addr[0]}:{addr[1]}",
                        "mail_from": mail_from,
                        "rcpt_tos": rcpt_tos,
                        "raw_bytes": len(raw),
                        "raw_preview": raw.decode("utf-8", errors="ignore")[:4000],
                    }
                )
                conn.sendall(b"250 OK: message accepted\r\n")
            elif upper.startswith("QUIT"):
                conn.sendall(b"221 Bye\r\n")
                break
            else:
                conn.sendall(b"500 unrecognized command\r\n")


def main() -> int:
    from app.services.email_mime_report_service import EmailIdentity
    from app.services.movimento_email.email_service import build_email_movimento_message
    from app.services.movimento_email.models import (
        ContextoEmailMovimento,
        ItemFechamento,
        ItemPendenciaCadastro,
        ItemPendenciaHistorica,
        ItemPendenciaObservacao,
    )
    from app.services.movimento_email.smtp_sender import SmtpEmailSender

    contexto = ContextoEmailMovimento(
        data_referencia=date.today(),
        correlation_id="evidence-smtp-capture-local",
        fechamento=[ItemFechamento(indicador="Propostas fechadas", valor="0", observacao="dados sintéticos de evidência")],
        pendencias_cadastro=[
            ItemPendenciaCadastro(
                protocolo="SINTETICO-0001", cliente="Cliente Teste", cpf="000.000.000-00",
                pendencia="Evidência de mecanismo de envio", dias_em_aberto=0, responsavel="evidence-script",
            )
        ],
        pendencias_historicas=[ItemPendenciaHistorica(periodo_referencia="N/A", pendencia="N/A", quantidade=0, percentual=0.0)],
        pendencias_observacao=[
            ItemPendenciaObservacao(
                protocolo="SINTETICO-0001", tipo_inconsistencia="N/A",
                descricao="Mensagem gerada apenas para validar o mecanismo real de envio SMTP", etapa="evidencia",
            )
        ],
    )
    message = build_email_movimento_message(
        sender=EmailIdentity(email="noreply@localhost", name="ReqSys"),
        recipients=[EmailIdentity(email="dev@localhost", name="Evidência Local")],
        contexto=contexto,
    )

    server = _CapturingSMTPServer(HOST, PORT)
    stop_event = threading.Event()
    loop_thread = threading.Thread(target=server.serve_one, args=(stop_event,), daemon=True)
    loop_thread.start()
    time.sleep(0.2)

    sender = SmtpEmailSender(host=HOST, port=PORT, username="", password="", use_tls=False, max_retries=1)
    error: str | None = None
    try:
        sender.enviar(message)
    except Exception as exc:  # noqa: BLE001 - queremos registrar qualquer falha na evidência
        error = str(exc)
    finally:
        time.sleep(0.2)
        stop_event.set()
        loop_thread.join(timeout=5)
        server.close()

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "schema_version": "1.0.0",
        "kind": "local-smtp-mechanism-evidence",
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "purpose": (
            "Valida que SmtpEmailSender + build_email_movimento_message (codigo de producao) "
            "completam um envio SMTP real via socket contra um receptor SMTP real. "
            "NAO substitui a validacao contra o SMTP corporativo real (P0-02), que depende "
            "de MOVIMENTO_EMAIL_SMTP_* reais, ainda pendentes."
        ),
        "smtp_target": f"{HOST}:{PORT}",
        "send_error": error,
        "send_succeeded": error is None,
        "messages_received_by_capture_server": server.captured,
    }
    summary_path = ARTIFACT_DIR / "local-smtp-mechanism-evidence.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if error is None and server.captured else 1


if __name__ == "__main__":
    raise SystemExit(main())
