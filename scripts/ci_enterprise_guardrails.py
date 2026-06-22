#!/usr/bin/env python3
"""Guardrails determinísticos de CI para maturidade enterprise contínua.

Objetivo:
- detectar causas recorrentes de CI instável antes de executar testes caros;
- bloquear configurações inseguras ou não determinísticas apenas em código runtime/config produtivo;
- evitar falsos positivos em testes, fixtures, documentação, exemplos e mensagens de validação;
- gerar relatório legível para artifact e GitHub Step Summary.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
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
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".vue",
    ".json",
    ".yml",
    ".yaml",
    ".md",
    ".toml",
    ".ini",
    ".cfg",
    ".env",
    ".example",
    ".txt",
    ".html",
    ".css",
}
TEST_OR_EXAMPLE_MARKERS = {
    "test",
    "tests",
    "__tests__",
    "spec",
    "specs",
    "fixture",
    "fixtures",
    "mock",
    "mocks",
    "example",
    "examples",
    "sample",
    "samples",
    "demo",
    "demos",
}
DOCUMENTATION_EXTENSIONS = {".md", ".txt"}
DOCUMENTATION_DIRS = {"docs", "doc", "documentation", "adr"}
PRODUCTION_CONFIG_DIRS = {"config", "configs", "deploy", "deployment", "infra", "nginx"}
RUNTIME_CODE_MARKERS = {"app", "backend", "frontend", "src", "server", "api", "services", "core"}
VALIDATION_OR_UI_MESSAGE_PATTERNS = (
    "errors.",
    "error.",
    "errMsg",
    "erro.set",
    "mat-error",
    "required",
    "obrigatório",
    "obrigatoria",
    "obrigatória",
    "inválid",
    "invalid",
    "credenciais inválidas",
)


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
        if path.suffix.lower() in TEXT_EXTENSIONS or path.name in {
            "Dockerfile",
            "requirements.txt",
            "package-lock.json",
            "pnpm-lock.yaml",
        }:
            yield path


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1", errors="ignore")


def relative_path(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def path_parts_lower(path: Path) -> set[str]:
    rel = Path(relative_path(path))
    return {part.lower() for part in rel.parts}


def is_test_or_example(path: Path) -> bool:
    rel = relative_path(path).lower()
    parts = path_parts_lower(path)
    name = path.name.lower()
    return (
        bool(parts & TEST_OR_EXAMPLE_MARKERS)
        or ".test." in name
        or ".spec." in name
        or name.startswith("test_")
        or name.endswith("_test.py")
        or name.endswith("_spec.py")
        or "/fixtures/" in rel
        or "/mocks/" in rel
        or rel.endswith(".example")
        or rel.endswith(".env.example")
    )


def is_documentation(path: Path) -> bool:
    parts = path_parts_lower(path)
    return path.suffix.lower() in DOCUMENTATION_EXTENSIONS or bool(parts & DOCUMENTATION_DIRS)


def is_runtime_or_production_config(path: Path) -> bool:
    parts = path_parts_lower(path)
    if is_test_or_example(path) or is_documentation(path):
        return False
    return bool(parts & RUNTIME_CODE_MARKERS) or bool(parts & PRODUCTION_CONFIG_DIRS) or path.name in {
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        "fly.toml",
        "nginx.conf",
    }


def is_validation_or_ui_message(line: str) -> bool:
    lowered = line.lower()
    return any(marker.lower() in lowered for marker in VALIDATION_OR_UI_MESSAGE_PATTERNS)


def add(
    finds: list[Finding],
    severity: str,
    rule: str,
    path: Path,
    line: int,
    message: str,
    recommendation: str,
) -> None:
    finds.append(
        Finding(
            severity=severity,
            rule=rule,
            path=relative_path(path),
            line=line,
            message=message,
            recommendation=recommendation,
        )
    )


def check_workflow_determinism(finds: list[Finding]) -> None:
    workflow_dir = ROOT / ".github" / "workflows"
    if not workflow_dir.exists():
        return

    for path in workflow_dir.glob("*.yml"):
        content = read_text(path)
        for index, line in enumerate(content.splitlines(), start=1):
            lowered = line.lower()
            if "node-version:" in lowered and "latest" in lowered:
                add(finds, "error", "CI_DETERMINISM_NODE", path, index, "Workflow usa Node latest.", "Fixar versão explícita compatível com o projeto.")
            if re.search(r"uses:\s*actions/(checkout|setup-node|setup-python)@main\b", line):
                add(finds, "error", "CI_DETERMINISM_ACTION_REF", path, index, "Action usa branch mutável.", "Usar versão maior fixada, como @v4 ou @v5.")
            if re.search(r"\bnpm install\b", line) and "npm install -g" not in line:
                add(finds, "warning", "CI_DETERMINISM_NPM_INSTALL", path, index, "Workflow usa npm install.", "Usar npm ci quando houver package-lock.json. Manter npm install apenas como fallback documentado.")
            if "continue-on-error: true" in lowered:
                add(finds, "warning", "CI_GOVERNANCE_CONTINUE_ON_ERROR", path, index, "Job/step tolera erro silenciosamente.", "Usar apenas em coleta de evidências, nunca em gate obrigatório.")


def classify_security_severity(path: Path) -> str | None:
    if is_test_or_example(path):
        return None
    if is_documentation(path):
        return "warning"
    if is_runtime_or_production_config(path):
        return "error"
    return "warning"


def check_security_gates(finds: list[Finding]) -> None:
    patterns = [
        ("SECURITY_AUTH_DISABLED", re.compile(r"(?i)(auth|authentication|msal|jwt)[\w.-]*(disabled|enabled)?\s*[:=]\s*(false|0|off)"), "Não versionar autenticação desligada como padrão em runtime/config produtivo."),
        ("SECURITY_CORS_WILDCARD", re.compile(r"(?i)(allow_origins|allowed_origins|cors|origins?)\s*[:=]\s*['\"]?\*['\"]?"), "Não permitir CORS '*' em produção."),
        ("SECURITY_JWT_DISABLED", re.compile(r"(?i)(verify_signature|validate_issuer|validate_audience)\s*[:=]\s*(false|0)"), "Issuer, audience e assinatura JWT devem ser validados em runtime/config produtivo."),
        ("SECURITY_SECRET_LITERAL", re.compile(r"(?i)(client_secret|password|senha|token|api_key)\s*[:=]\s*['\"][^'\"]{8,}['\"]"), "Usar secret manager/variáveis protegidas e exemplos mascarados."),
    ]

    for path in iter_files():
        if path.name == "ci_enterprise_guardrails.py":
            continue

        severity = classify_security_severity(path)
        if severity is None:
            continue

        content = read_text(path)
        for index, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "//", "*", "<!--")):
                continue
            for rule, pattern, recommendation in patterns:
                if rule == "SECURITY_SECRET_LITERAL" and is_validation_or_ui_message(line):
                    continue
                if pattern.search(line):
                    add(finds, severity, rule, path, index, "Possível configuração sensível/insegura versionada.", recommendation)


def check_lockfiles(finds: list[Finding]) -> None:
    package_jsons = (
        list(ROOT.glob("package.json"))
        + list((ROOT / "frontend").glob("package.json"))
        + list((ROOT / "backend").glob("package.json"))
    )
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
        lines.append(f"| {finding.severity} | `{finding.rule}` | `{finding.path}` | {finding.line} | {finding.message} | {finding.recommendation} |")
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
