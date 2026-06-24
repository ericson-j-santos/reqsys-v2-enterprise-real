#!/usr/bin/env python3
"""Enterprise Runtime Governance Gates.

Scanner preventivo para bloquear padrões incompatíveis com entrega enterprise.
Escopo v2: runtime/config real, com exclusão explícita de docs, testes, fixtures, mocks e exemplos.
Sempre publica relatório markdown/json para artifact e GitHub Step Summary.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "artifacts" / "enterprise-runtime-governance"

IGNORED_DIRS = {
    ".git", ".github/actions-cache", ".venv", "venv", "node_modules", "dist", "build", "target",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "coverage", "htmlcov", ".next", ".nuxt",
    "docs", "test", "tests", "__tests__", "spec", "specs", "fixture", "fixtures", "mock", "mocks",
    "example", "examples", "sample", "samples", "demo", "demos",
}

IGNORED_FILE_PATTERNS = (
    re.compile(r"(^|/).*\.test\.", re.IGNORECASE),
    re.compile(r"(^|/).*\.spec\.", re.IGNORECASE),
    re.compile(r"(^|/)test_.*", re.IGNORECASE),
    re.compile(r"(^|/).*_test\.py$", re.IGNORECASE),
    re.compile(r"(^|/).*_spec\.py$", re.IGNORECASE),
    re.compile(r".*\.env\.example$", re.IGNORECASE),
    re.compile(r".*\.example$", re.IGNORECASE),
)

TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".cs", ".kt", ".go",
    ".yml", ".yaml", ".json", ".sh", ".env", ".properties", ".toml", ".ini", ".html", ".css",
}

ALLOWLIST_PATTERNS = [
    re.compile(r"example", re.IGNORECASE),
    re.compile(r"placeholder", re.IGNORECASE),
    re.compile(r"dummy", re.IGNORECASE),
    re.compile(r"changeme", re.IGNORECASE),
    re.compile(r"scripts/governance/enterprise_runtime_governance_gates.py"),
]

BLOCKING_SEVERITIES = {"HIGH"}
OPERATIONAL_CODE_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".cs", ".go"}


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
        re.compile(r"(?i)(allowed[_-]?origins|cors|Access-Control-Allow-Origin).{0,80}(\*|['\"]\*['\"])") ,
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


def relative_path(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def is_ignored(path: Path) -> bool:
    relative = relative_path(path)
    if set(Path(relative).parts) & IGNORED_DIRS:
        return True
    return any(pattern.search(relative) for pattern in IGNORED_FILE_PATTERNS)


def is_text_candidate(path: Path) -> bool:
    return path.is_file() and not is_ignored(path) and path.suffix in TEXT_EXTENSIONS


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def is_allowlisted(path: str, line: str) -> bool:
    return any(pattern.search(f"{path}:{line}") for pattern in ALLOWLIST_PATTERNS)


def iter_files() -> Iterable[Path]:
    for path in ROOT.rglob("*"):
        if is_text_candidate(path):
            yield path


def scan_content(path: Path, content: str) -> list[Finding]:
    findings: list[Finding] = []
    relative = relative_path(path)
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
    for path in operational_files:
        content = read_text(path)
        if content and "correlation_id" in content:
            return []
    return [Finding("MEDIUM", "OBS_CORRELATION_ID_MISSING", ".", 0, "Nenhuma referência a correlation_id encontrada no código operacional.")]


def write_reports(findings: list[Finding], scanned_files: int) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    blocking = [finding for finding in findings if finding.severity in BLOCKING_SEVERITIES]
    warnings = [finding for finding in findings if finding.severity not in BLOCKING_SEVERITIES]
    status = "failed" if blocking else "passed"

    payload = {
        "status": status,
        "summary": {
            "scanned_files": scanned_files,
            "blocking": len(blocking),
            "warnings": len(warnings),
            "findings": len(findings),
        },
        "findings": [asdict(finding) for finding in findings],
    }
    (REPORT_DIR / "enterprise-runtime-governance.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Enterprise Runtime Governance Gates",
        "",
        f"Status: **{status}**",
        "",
        "| Métrica | Valor |",
        "|---|---:|",
        f"| Arquivos escaneados | {scanned_files} |",
        f"| Bloqueios | {len(blocking)} |",
        f"| Warnings | {len(warnings)} |",
        "",
        "| Severidade | Código | Arquivo | Linha | Mensagem |",
        "|---|---|---|---:|---|",
    ]
    if findings:
        lines.extend(f"| {f.severity} | `{f.code}` | `{f.path}` | {f.line} | {f.message} |" for f in findings)
    else:
        lines.append("| info | `OK` | — | — | Nenhum desvio bloqueante encontrado. |")

    markdown = "\n".join(lines) + "\n"
    (REPORT_DIR / "enterprise-runtime-governance.md").write_text(markdown, encoding="utf-8")
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write(markdown)


def main() -> int:
    files = list(iter_files())
    findings: list[Finding] = []
    for path in files:
        content = read_text(path)
        if content is not None:
            findings.extend(scan_content(path, content))
    findings.extend(scan_correlation_id_presence(files))
    write_reports(findings, len(files))

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
    print(f"[INFO] Relatório: {REPORT_DIR.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
