#!/usr/bin/env python3
"""Resumo rápido da execução real do P0 de Prospecção Movimento.

Objetivo: reduzir a perda de tempo em validações repetidas e padronizar a
classificação do estado do trabalho em um único comando.

Saída:
- local_ok: backend/frontend funcionando
- external_blocked: faltam DSN SMTP reais
- ready_for_handoff: etapa pronta para equipe externa/infra
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib import request
from urllib.error import URLError, HTTPError

ROOT = Path(__file__).resolve().parents[1]


def _read_dotenv(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def _env_value(*names: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip():
            return value.strip()
    env_data = _read_dotenv(ROOT / '.env')
    for name in names:
        value = env_data.get(name)
        if value:
            return value.strip()
    return ''


def _http_probe(url: str, timeout: int = 5) -> tuple[bool, int | None, str]:
    try:
        with request.urlopen(request.Request(url, method='GET'), timeout=timeout) as resp:
            return True, resp.status, url
    except (HTTPError, URLError, TimeoutError, ConnectionError) as exc:
        return False, None, str(exc)


def main() -> int:
    print('=== Resumo de execução P0 ===')
    backend_url = 'http://127.0.0.1:8000/health'
    frontend_urls = ['http://127.0.0.1:5173/', 'http://127.0.0.1:5174/']

    backend_ok, backend_status, backend_msg = _http_probe(backend_url)
    frontend_ok = False
    frontend_url = ''
    for candidate in frontend_urls:
        ok, status, msg = _http_probe(candidate)
        if ok:
            frontend_ok = True
            frontend_url = candidate
            frontend_status = status
            frontend_msg = msg
            break
        frontend_msg = msg
    
    dsn_ok = bool(_env_value('MOVIMENTO_EMAIL_SOURCE_DSN'))
    smtp_host = _env_value('MOVIMENTO_EMAIL_SMTP_HOST')
    smtp_user = _env_value('MOVIMENTO_EMAIL_SMTP_USER')
    smtp_from = _env_value('MOVIMENTO_EMAIL_SMTP_FROM')
    smtp_ok = bool(smtp_host and smtp_user and smtp_from)

    print(f'Backend local: {"OK" if backend_ok else "BLOQUEADO"} -> {backend_url} ({backend_status or "sem resposta"})')
    if frontend_ok:
        print(f'Frontend local: OK -> {frontend_url} ({frontend_status})')
    else:
        print(f'Frontend local: BLOQUEADO -> {frontend_urls} ({frontend_msg})')
    print(f'DSN SQL Server: {"OK" if dsn_ok else "FALTA"}')
    print(f'SMTP real: {"OK" if smtp_ok else "FALTA"}')

    if not backend_ok or not frontend_ok:
        print('\nAção: corrigir runtime local antes de continuar, porque o ambiente local ainda não está saudável.')
        return 1

    if not dsn_ok or not smtp_ok:
        print('\nEstado: local_ok=true, external_blocked=true')
        print('Ação objetiva: pedir ao time de dados/infra o MOVIMENTO_EMAIL_SOURCE_DSN e ao time de e-mail as variáveis SMTP reais.')
        print('Quando tudo vier, usar:')
        print('  1) python scripts/verificar_movimento_email_fontes.py status')
        print('  2) python scripts/verificar_movimento_email_fontes.py verificar')
        print('  3) pytest backend/tests/test_movimento_email_api.py -q')
        print('  4) validar envio SMTP em dry_run=true')
        return 0

    print('\nEstado: local_ok=true, external_ok=true, pronto para validação real do fluxo completo.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
