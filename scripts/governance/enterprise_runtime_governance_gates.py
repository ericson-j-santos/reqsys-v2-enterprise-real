#!/usr/bin/env python3
"""Enterprise Runtime Governance Gates.

Scanner preventivo para bloquear padrões incompatíveis com entrega enterprise:
- secrets e tokens hardcoded;
- CORS wildcard;
- verify=False;
- HTTP inseguro em contexto produtivo;
- logs com PII/LGPD;
- connection strings expostas;
- ausência de correlation_id em código operacional.

Diretriz de escopo v1:
- bloquear apenas violações HIGH em artefatos operacionais/configuracionais;
- tratar achados MEDIUM como warnings;
- evitar varrer documentação Markdown para reduzir falso positivo em runbooks/ADRs.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]

IGNORED_DIRS = {
    ".git",
    ".github/actions-cache",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "target",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "coverage",
    ".next",
    ".nuxt",
    "docs",
}

TEXT_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".cs",
    ".kt",
    ".go",
    ".yml",
    ".yaml",
    ".json",
    ".sh",
    ".env",
    ".properties",
    ".toml",
    ".ini",
    ".html",
    ".css",
}

ALLOWLIST_PATTERNS = [
    re.compile(r"example", re.IGNORECASE),
    re.compile(r"placeholder", re.IGNORECASE),
    re.compile(r"dummy", re.IGNORECASE),
    re.compile(r"changeme", re.IGNORECASE),
    re.compile(r"scripts/governance/enterprise_runtime_governance_gates.py"),
]

BLOCKING_SEVERITIES = {"HIGH"}

@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    path: str
    line: int
    message: str


RULES: list[tuple[str, str, re.Pattern[str], str]] = [
    (
        "HIGH",
        "SEC_SECRET_HARDCODED",
        re.compile(r"(?i)(password|passwd|pwd|secret|api[_-]?key|token)\s*[:=]\s*['\"][^'\"]{8,}['\"]"),
        "Possível segredo/token hardcoded.",
    ),
    (
        "HIGH",
        "SEC_CORS_WILDCARD",
        re.compile(r"(?i)(allowed[_-]?origins|cors|Access-Control-Allow-Origin).{0,80}(\*|['\"]\*['\"])"),
        "Possível CORS wildcard.",
    ),
    (
        "HIGH",
        "SEC_TLS_VERIFY_FALSE",
        re.compile(r"(?i)verify\s*=\s*false"),
        "TLS verification desabilitada.",
    ),
    (
        "MEDIUM",
        "SEC_HTTP_INSECURE",
        re.compile(r"http://(?!localhost|127\.0\.0\.1|0\.0\.0\.0)"),
        "URL HTTP insegura fora de localhost.",
    ),
    (
        "HIGH",
        "LGPD_PII_LOGGING",
        re.compile(r"(?i)(log|logger|console\.(log|error|warn)|print)\s*\(.*(cpf|cnpj|password|token|secret|senha)"),
        "Possível log de PII/segredo.",
    ),
    (
        "HIGH",
        "SEC_CONNECTION_STRING",
        re.compile(r"(?i)(Server=|Data Source=|User ID=|Password=|mongodb\+srv://|postgres://|mysql://|jdbc:sqlserver://)"),
        "Possível connection string exposta.",
    ),
]

OPERATIONAL_CODE_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".cs", ".go"}


def is_ignored(path: Path) -> bool:
    parts = set(path.relative_to(ROOT).parts)
    return bool(parts & IGNORED_DIRS)


def is_text_candidate(path: Path) -> bool:
    return path.is_file() and not is_ignored(path) and path.suffix in TEXT_EXTENSIONS


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def is_allowlisted(path: str, line: str) -> bool:
    value = f"{path}:{line}"
    return any(pattern.search(value) for pattern in ALLOWLIST_PATTERNS)


def iter_files() -> Iterable[Path]:
    for path in ROOT.rglob("*"):
        if is_text_candidate(path):
            yield path


def scan_content(path: Path, content: str) -> list[Finding]:
    findings: list[Finding] = []
    relative = path.relative_to(ROOT).as_posix()

    for line_number, line in enumerate(content.splitlines(), start=1):
        if is_allowlisted(relative, line):
            continue
        for severity, code, pattern, message in RULES:
            if pattern.search(line):
                findings.append(Finding(severity, code, relative, line_number, message))

    return findings


def scan_correlation_id_presence(files: list[Path]) -> list[Finding]:
    operational_files = [path for path in files if path.suffix in OPERATIONAL_CODE_EXTENSIONS]
    if not operational_files:
        return []

    has_correlation = False
    for path in operational_files:
        content = read_text(path)
        if content and "correlation_id" in content:
            has_correlation = True
            break

    if has_correlation:
        return []

    return [
        Finding(
            "MEDIUM",
            "OBS_CORRELATION_ID_MISSING",
            ".",
            0,
            "Nenhuma referência a correlation_id encontrada no código operacional.",
        )
    ]


def main() -> int:
    files = list(iter_files())
    findings: list[Finding] = []

    for path in files:
        content = read_text(path)
        if content is None:
            continue
        findings.extend(scan_content(path, content))

    findings.extend(scan_correlation_id_presence(files))

    blocking = [finding for finding in findings if finding.severity in BLOCKING_SEVERITIES]
    warnings = [finding for finding in findings if finding.severity not in BLOCKING_SEVERITIES]

    for finding in warnings:
        location = f"{finding.path}:{finding.line}" if finding.line else finding.path
        print(f"[WARN] {finding.code} {location} — {finding.message}")

    if blocking:
        print("[FAIL] Enterprise Runtime Governance Gates encontraram violações bloqueantes:")
        for finding in blocking:
            location = f"{finding.path}:{finding.line}" if finding.line else finding.path
            print(f"- [{finding.severity}] {finding.code} {location} — {finding.message}")
        return 1

    print("[OK] Enterprise Runtime Governance Gates sem violações bloqueantes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
