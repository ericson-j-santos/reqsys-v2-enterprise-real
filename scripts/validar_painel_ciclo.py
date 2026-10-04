#!/usr/bin/env python3
"""Valida o painel central vivo do ReqSys sem aceitar estado operacional congelado."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "docs" / "painel-ciclo-completo-reqsys.html"
JSON_PATH = ROOT / "docs" / "ciclo-completo" / "estado-ciclo-reqsys.json"
PROJECTS_PATH = ROOT / "config" / "operational-dashboard-projects.json"

FORBIDDEN_EXTERNALS = [
    "cdn.",
    "unpkg.com",
    "jsdelivr.net",
    "fonts.googleapis.com",
    "cdnjs.cloudflare.com",
]
SENSITIVE_PATTERNS = [
    r"ghp_[A-Za-z0-9_]{20,}",
    r"github_pat_[A-Za-z0-9_]{20,}",
    r"AKIA[0-9A-Z]{16}",
    r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----",
    r"password\s*=\s*['\"][^'\"]{4,}['\"]",
    r"senha\s*=\s*['\"][^'\"]{4,}['\"]",
    r"Server\s*=.*;Database\s*=.*;(User Id|UID)\s*=.*;(Password|PWD)\s*=",
]
REQUIRED_PROJECTS = {
    "ericson-j-santos/reqsys-v2-enterprise-real",
    "ericson-j-santos/desktop-pc24x7-runtime",
    "ericson-j-santos/painel-powerbi",
    "ericson-j-santos/chatgpt-operational-rules",
}


def fail(message: str) -> None:
    print(f"FALHA: {message}")
    raise SystemExit(1)


def read_required(path: Path) -> str:
    if not path.exists():
        fail(f"Arquivo obrigatorio ausente: {path}")
    return path.read_text(encoding="utf-8")


def validate_contract(html: str, bootstrap: dict[str, Any], projects: dict[str, Any]) -> None:
    lower_html = html.lower()
    for forbidden in FORBIDDEN_EXTERNALS:
        if forbidden in lower_html:
            fail(f"HTML contem dependencia externa proibida: {forbidden}")

    combined = html + "\n" + json.dumps(bootstrap, ensure_ascii=False) + "\n" + json.dumps(
        projects, ensure_ascii=False
    )
    for pattern in SENSITIVE_PATTERNS:
        if re.search(pattern, combined, re.IGNORECASE | re.DOTALL):
            fail(f"Padrao sensivel detectado: {pattern}")

    if '<script id="estado-ciclo" type="application/json">' in html:
        fail("HTML voltou a embutir estado operacional estatico")
    if "global-status.json" not in html:
        fail("HTML nao consome o contrato vivo global-status.json")

    for marker in ("GitHub", "Microsoft Teams", "Certificação", "SLO", "TODO Global", "Runtime PC24x7", "Power BI"):
        if marker not in html:
            fail(f"Marcador operacional ausente no HTML: {marker}")

    if bootstrap.get("schema_version") != "2.0.0":
        fail("Bootstrap deve usar schema_version 2.0.0")
    if bootstrap.get("mode") != "bootstrap":
        fail("JSON versionado deve ser somente bootstrap, nunca estado operacional")
    forbidden_state_keys = {"frentes", "checks", "indicadores", "visao_executiva"}
    leaked = sorted(forbidden_state_keys.intersection(bootstrap))
    if leaked:
        fail("Bootstrap contem estado operacional congelado: " + ", ".join(leaked))

    repositories = projects.get("repositories")
    if not isinstance(repositories, list) or not repositories:
        fail("Configuração de projetos vazia")
    names = [str(item.get("repository") or "") for item in repositories if isinstance(item, dict)]
    if len(names) != len(set(names)):
        fail("Configuração de projetos contém repositório duplicado")
    missing = sorted(REQUIRED_PROJECTS.difference(names))
    if missing:
        fail("Projetos operacionais obrigatórios ausentes: " + ", ".join(missing))


def main() -> int:
    html = read_required(HTML_PATH)
    try:
        bootstrap = json.loads(read_required(JSON_PATH))
        projects = json.loads(read_required(PROJECTS_PATH))
    except json.JSONDecodeError as exc:
        fail(f"JSON invalido: {exc}")

    if not isinstance(bootstrap, dict) or not isinstance(projects, dict):
        fail("Contratos do painel devem ser objetos JSON")

    validate_contract(html, bootstrap, projects)

    print("OK: painel central vivo validado com sucesso")
    print(f"Arquivo HTML: {HTML_PATH}")
    print(f"Bootstrap: {JSON_PATH}")
    print(f"Projetos configurados: {len(projects['repositories'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
