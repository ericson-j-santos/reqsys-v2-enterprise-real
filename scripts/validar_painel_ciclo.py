#!/usr/bin/env python3
"""Valida o painel de acompanhamento do ciclo completo ReqSys."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "docs" / "painel-ciclo-completo-reqsys.html"
JSON_PATH = ROOT / "docs" / "ciclo-completo" / "estado-ciclo-reqsys.json"

FORBIDDEN_EXTERNALS = ["cdn.", "unpkg.com", "jsdelivr.net", "fonts.googleapis.com", "cdnjs.cloudflare.com"]
SENSITIVE_PATTERNS = [
    r"ghp_[A-Za-z0-9_]{20,}",
    r"github_pat_[A-Za-z0-9_]{20,}",
    r"AKIA[0-9A-Z]{16}",
    r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----",
    r"password\s*=\s*['\"][^'\"]{4,}['\"]",
    r"senha\s*=\s*['\"][^'\"]{4,}['\"]",
    r"Server\s*=.*;Database\s*=.*;(User Id|UID)\s*=.*;(Password|PWD)\s*=",
]


def fail(message: str) -> None:
    print(f"FALHA: {message}")
    raise SystemExit(1)


def read_required(path: Path) -> str:
    if not path.exists():
        fail(f"Arquivo obrigatorio ausente: {path}")
    return path.read_text(encoding="utf-8")


def main() -> int:
    html = read_required(HTML_PATH)
    raw_json = read_required(JSON_PATH)
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        fail(f"JSON invalido: {exc}")

    if '<script id="estado-ciclo" type="application/json">' not in html:
        fail("HTML nao contem JSON embutido do ciclo")

    lower_html = html.lower()
    for forbidden in FORBIDDEN_EXTERNALS:
        if forbidden in lower_html:
            fail(f"HTML contem dependencia externa proibida: {forbidden}")

    combined = html + "\n" + raw_json
    for pattern in SENSITIVE_PATTERNS:
        if re.search(pattern, combined, re.IGNORECASE | re.DOTALL):
            fail(f"Padrao sensivel detectado: {pattern}")

    frentes = data.get("frentes", [])
    tracked_prs = {item.get("pr") for item in frentes if item.get("pr")}
    missing_prs = {18, 19, 20} - tracked_prs
    if missing_prs:
        fail(f"PRs obrigatorios nao rastreados: {sorted(missing_prs)}")

    if data.get("issue_tracker", {}).get("issue") != 21:
        fail("Issue #21 nao esta registrada como tracker do painel")

    gates = data.get("visao_executiva", {}).get("gates_bloqueantes", [])
    if len(gates) < 8:
        fail("Quantidade minima de gates bloqueantes nao atendida")

    print("OK: painel de ciclo validado com sucesso")
    print(f"Arquivo HTML: {HTML_PATH}")
    print(f"Arquivo JSON: {JSON_PATH}")
    print(f"Frentes rastreadas: {len(frentes)}")
    print(f"PRs rastreados: {sorted(tracked_prs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
