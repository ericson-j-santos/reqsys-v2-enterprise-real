#!/usr/bin/env python3
"""Guardrails determinísticos de CI para maturidade enterprise contínua.

Objetivo:
- detectar causas recorrentes de CI instável antes de executar testes caros;
- bloquear configurações inseguras ou não determinísticas;
- gerar relatório legível para artifact e GitHub Step Summary.
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "coverage",
    "htmlcov",
}
TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".vue", ".json", ".yml", ".yaml",
    ".md", ".toml", ".ini", ".cfg", ".env", ".example", ".txt", ".html", ".css",
}


@dataclass(frozen=True)
class Finding:
    severity: str
    rule: str
    path: str
    line: int
    message: str
    recommendation: str


def iter_files() -> Iterable[Path]:
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in TEXT_EXTENSIONS or path.name in {"Dockerfile", "requirements.txt", "package-lock.json", "pnpm-lock.yaml"}:
            yield path


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1", errors="ignore")


def add(finds: list[Finding], severity: str, rule: str, path: Path, line: int, message: str, recommendation: str) -> None:
    finds.append(
        Finding(
            severity=severity,
            rule=rule,
            path=str(path.relative_to(ROOT)),
            line=line,
            message=message,
            recommendation=recommendation,
        )
    )


def check_workflow_determinism(finds: list[Finding]) -> None:
    for path in (ROOT / ".github" / "workflows").glob("*.yml"):
        content = read_text(path)
        for index, line in enumerate(content.splitlines(), start=1):
            lowered = line.lower()
            if "node-version:" in lowered and "latest" in lowered:
                add(finds, "error", "CI_DETERMINISM_NODE", path, index, "Workflow usa Node latest.", "Fixar versão explícita, preferencialmente 20.14.0 ou versão definida no projeto.")
            if re.search(r"uses:\s*actions/(checkout|setup-node|setup-python)@main\b", line):
                add(finds, "error", "CI_DETERMINISM_ACTION_REF", path, index, "Action usa branch mutável.", "Usar versão maior fixada, como @v4 ou @v5.")
            if re.search(r"\bnpm install\b", line) and "npm install -g" not in line:
                add(finds, "warning", "CI_DETERMINISM_NPM_INSTALL", path, index, "Workflow usa npm install.", "Usar npm ci quando houver package-lock.json.")
            if "continue-on-error: true" in lowered:
                add(finds, "warning", "CI_GOVERNANCE_CONTINUE_ON_ERROR", path, index, "Job/step tolera erro silenciosamente.", "Usar apenas em coleta de evidências, nunca em gate obrigatório.")


def check_security_gates(finds: list[Finding]) -> None:
    patterns = [
        ("SECURITY_AUTH_DISABLED", re.compile(r"(?i)(auth|authentication|msal|jwt)[\w.-]*(disabled|enabled)?\s*[:=]\s*(false|0|off)"), "Não versionar autenticação desligada como padrão."),
        ("SECURITY_CORS_WILDCARD", re.compile(r"(?i)(allow_origins|allowed_origins|cors|origins?)\s*[:=]\s*['\"]?\*['\"]?"), "Não permitir CORS '*' em produção."),
        ("SECURITY_JWT_DISABLED", re.compile(r"(?i)(verify_signature|validate_issuer|validate_audience)\s*[:=]\s*(false|0)"), "Issuer, audience e assinatura JWT devem ser validados."),
        ("SECURITY_SECRET_LITERAL", re.compile(r"(?i)(client_secret|password|senha|token|api_key)\s*[:=]\s*['\"][^'\"]{8,}['\"]"), "Usar secret manager/variáveis protegidas e exemplos mascarados."),
    ]
    for path in iter_files():
        rel = str(path.relative_to(ROOT))
        if rel.endswith("ci_enterprise_guardrails.py"):
            continue
        content = read_text(path)
        for index, line in enumerate(content.splitlines(), start=1):
            if "example" in rel.lower() or ".md" in rel.lower():
                continue
            for rule, pattern, recommendation in patterns:
                if pattern.search(line):
                    add(finds, "error", rule, path, index, "Possível configuração sensível/insegura versionada.", recommendation)


def check_lockfiles(finds: list[Finding]) -> None:
    package_jsons = list(ROOT.glob("package.json")) + list((ROOT / "frontend").glob("package.json")) + list((ROOT / "backend").glob("package.json"))
    for package_json in package_jsons:
        folder = package_json.parent
        has_lock = any((folder / lock).exists() for lock in ("package-lock.json", "pnpm-lock.yaml", "yarn.lock"))
        if not has_lock:
            add(finds, "warning", "CI_LOCKFILE_MISSING", package_json, 1, "package.json sem lockfile no mesmo diretório.", "Adicionar package-lock.json/pnpm-lock.yaml para builds determinísticos.")


def write_reports(findings: list[Finding]) -> None:
    report_dir = ROOT / "ci-reports"
    report_dir.mkdir(exist_ok=True)
    payload = {
        "status": "failed" if any(f.severity == "error" for f in findings) else "passed",
        "summary": {
            "errors": sum(1 for f in findings if f.severity == "error"),
            "warnings": sum(1 for f in findings if f.severity == "warning"),
            "findings": len(findings),
        },
        "findings": [asdict(f) for f in findings],
    }
    (report_dir / "ci-enterprise-guardrails.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# CI Enterprise Guardrails",
        "",
        f"Status: **{payload['status']}**",
        "",
        "| Severidade | Regra | Arquivo | Linha | Mensagem | Recomendação |",
        "|---|---|---|---:|---|---|",
    ]
    for finding in findings:
        lines.append(
            f"| {finding.severity} | `{finding.rule}` | `{finding.path}` | {finding.line} | {finding.message} | {finding.recommendation} |"
        )
    if not findings:
        lines.append("| info | `OK` | — | — | Nenhum desvio bloqueante encontrado. | Manter monitoramento contínuo. |")
    markdown = "\n".join(lines) + "\n"
    (report_dir / "ci-enterprise-guardrails.md").write_text(markdown, encoding="utf-8")

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write(markdown)


def main() -> int:
    findings: list[Finding] = []
    check_workflow_determinism(findings)
    check_lockfiles(findings)
    check_security_gates(findings)
    write_reports(findings)

    errors = [f for f in findings if f.severity == "error"]
    if errors:
        print(f"CI Enterprise Guardrails falhou com {len(errors)} erro(s). Consulte ci-reports/ci-enterprise-guardrails.md")
        return 1

    print("CI Enterprise Guardrails aprovado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
