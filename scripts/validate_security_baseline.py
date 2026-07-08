#!/usr/bin/env python3
"""
Validador de baseline de segurança do ReqSys.

Objetivo:
- Executar offline/read-only no CI.
- Detectar riscos críticos comuns antes de merge/deploy.
- Gerar evidência JSON e Markdown rastreável.

Escopo inicial:
- Secret scanning heurístico.
- Hardcode MSAL/Azure e URLs de ambiente.
- CORS permissivo.
- TLS inseguro em Python.
- Logs com tokens/PII provável.
- Arquivos .env reais versionados.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT_DEFAULT = Path(__file__).resolve().parents[1]

IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "coverage",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "artifacts",
}

TEXT_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".vue",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
    ".ini",
    ".env",
    ".md",
    ".html",
    ".css",
    ".sh",
    ".ps1",
    ".bat",
    ".txt",
}

SAFE_FILE_NAMES = {
    ".env.example",
    ".env.exemplo",
    "env.example",
    "env.exemplo",
    "README.md",
    "SECURITY_BASELINE.md",
}

ALLOWLIST_PATH_PARTS = {
    "docs/changelog",
    "docs/security/SECURITY_BASELINE.md",
    "scripts/validate_security_baseline.py",
}


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    path: str
    line: int
    evidence: str
    recommendation: str


def is_ignored_path(path: Path) -> bool:
    parts = set(path.parts)
    if parts.intersection(IGNORED_DIRS):
        return True
    normalized = path.as_posix()
    return any(part in normalized for part in ALLOWLIST_PATH_PARTS)


def is_text_file(path: Path) -> bool:
    if path.name in SAFE_FILE_NAMES:
        return True
    return path.suffix.lower() in TEXT_EXTENSIONS


def normalize_repo_path(value: str) -> str:
    return value.strip().replace("\\", "/").lstrip("./")


def load_changed_file_paths(changed_files_path: Path) -> set[str]:
    if not changed_files_path.exists():
        return set()
    return {
        normalize_repo_path(line)
        for line in changed_files_path.read_text(encoding="utf-8").splitlines()
        if normalize_repo_path(line)
    }


def iter_files(root: Path, include_paths: set[str] | None = None) -> Iterable[Path]:
    if include_paths is not None:
        for relative_path in sorted(include_paths):
            path = (root / relative_path).resolve()
            try:
                path.relative_to(root)
            except ValueError:
                continue
            if path.is_file() and not is_ignored_path(path.relative_to(root)) and is_text_file(path):
                yield path
        return

    for path in root.rglob("*"):
        relative_path = path.relative_to(root)
        if path.is_file() and not is_ignored_path(relative_path) and is_text_file(path):
            yield path


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1", errors="ignore")


def compact_evidence(line: str) -> str:
    value = line.strip()
    value = re.sub(r"(?i)(authorization\s*[:=]\s*)([^\s'\"]+)", r"\1[REDACTED]", value)
    value = re.sub(r"(?i)((client_secret|api[_-]?key|token|password|senha)\s*[:=]\s*)([^\s'\"]+)", r"\1[REDACTED]", value)
    return value[:240]


def add_finding(findings: list[Finding], rule_id: str, severity: str, path: Path, root: Path, line_no: int, line: str, recommendation: str) -> None:
    findings.append(
        Finding(
            rule_id=rule_id,
            severity=severity,
            path=path.relative_to(root).as_posix(),
            line=line_no,
            evidence=compact_evidence(line),
            recommendation=recommendation,
        )
    )


def scan_env_files(root: Path, findings: list[Finding], include_paths: set[str] | None = None) -> None:
    for path in iter_files(root, include_paths=include_paths):
        name = path.name.lower()
        if name == ".env" or name.startswith(".env.") and name not in {".env.example", ".env.exemplo"}:
            add_finding(
                findings,
                "SEC-ENV-001",
                "critical",
                path,
                root,
                1,
                path.name,
                "Remover arquivo .env real do versionamento e usar GitHub Secrets/ambiente segregado.",
            )


def scan_lines(root: Path, findings: list[Finding], include_paths: set[str] | None = None) -> None:
    secret_patterns = [
        ("SEC-SECRET-001", re.compile(r"(?i)(client_secret|api[_-]?key|private[_-]?key|access[_-]?token|refresh[_-]?token|password|senha)\s*[:=]\s*['\"][^'\"]{8,}['\"]")),
        ("SEC-SECRET-002", re.compile(r"(?i)authorization\s*[:=]\s*['\"]?bearer\s+[a-z0-9._\-]{20,}")),
        ("SEC-SECRET-003", re.compile(r"(?i)-----BEGIN (RSA |EC |OPENSSH |)PRIVATE KEY-----")),
    ]

    msal_hardcode = re.compile(r"(?i)(clientId|client_id|tenantId|tenant_id|redirectUri|redirect_uri)\s*[:=]\s*['\"][^'\"]+['\"]")
    env_url = re.compile(r"https://reqsys-[a-z0-9\-]+\.fly\.dev|https://reqsys-app(?:-[a-z]+)?\.fly\.dev", re.I)
    cors_wildcard = re.compile(r"(?i)(allow_origins\s*=\s*\[\s*['\"]\*['\"]\s*\]|Access-Control-Allow-Origin\s*[:=]\s*['\"]\*['\"])" )
    tls_disabled = re.compile(r"(?i)(verify\s*=\s*False|NODE_TLS_REJECT_UNAUTHORIZED\s*=\s*['\"]?0['\"]?)")
    risky_log = re.compile(r"(?i)(print|logger\.|console\.)[^\n]*(authorization|access_token|refresh_token|client_secret|password|senha|cpf)")

    for path in iter_files(root, include_paths=include_paths):
        content = read_text(path)
        for line_no, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("//"):
                continue

            for rule_id, pattern in secret_patterns:
                if pattern.search(line):
                    add_finding(
                        findings,
                        rule_id,
                        "critical",
                        path,
                        root,
                        line_no,
                        line,
                        "Mover segredo para GitHub Secrets/secret manager e consumir por variável de ambiente.",
                    )
            if cors_wildcard.search(line):
                add_finding(
                    findings,
                    "SEC-CORS-001",
                    "critical",
                    path,
                    root,
                    line_no,
                    line,
                    "Substituir wildcard por ALLOWED_ORIGINS segregado por DEV/STG/PROD.",
                )
            if tls_disabled.search(line):
                add_finding(
                    findings,
                    "SEC-TLS-001",
                    "critical",
                    path,
                    root,
                    line_no,
                    line,
                    "Manter validação TLS habilitada e configurar CA corporativa quando necessário.",
                )
            if msal_hardcode.search(line) and "os.environ" not in line and "import.meta.env" not in line and "process.env" not in line:
                add_finding(
                    findings,
                    "SEC-MSAL-001",
                    "high",
                    path,
                    root,
                    line_no,
                    line,
                    "Parametrizar MSAL via variáveis por ambiente: client_id, tenant_id, redirect_uri e scopes.",
                )
            if env_url.search(line) and "example" not in path.name.lower() and ".md" != path.suffix.lower():
                add_finding(
                    findings,
                    "SEC-CONFIG-001",
                    "high",
                    path,
                    root,
                    line_no,
                    line,
                    "Remover URL de ambiente hardcoded e usar variável API_BASE_URL/PUBLIC_BASE_URL.",
                )
            if risky_log.search(line):
                add_finding(
                    findings,
                    "SEC-LOG-001",
                    "high",
                    path,
                    root,
                    line_no,
                    line,
                    "Aplicar sanitização central de logs para tokens, CPF, e-mail e payload sensível.",
                )


def summarize(findings: list[Finding]) -> dict[str, int]:
    summary = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for finding in findings:
        summary[finding.severity] = summary.get(finding.severity, 0) + 1
    return summary


def write_reports(findings: list[Finding], root: Path, output_dir: Path, scan_scope: str, scanned_files: int) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = summarize(findings)
    status = "failed" if summary.get("critical", 0) > 0 else "passed"
    payload = {
        "schema_version": "1.1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "scan_scope": scan_scope,
        "scanned_files": scanned_files,
        "summary": summary,
        "findings": [asdict(finding) for finding in findings],
    }
    (output_dir / "security-baseline-report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Security Baseline Gate",
        "",
        f"Status: **{status.upper()}**",
        "",
        "## Escopo",
        "",
        f"- Modo: `{scan_scope}`",
        f"- Arquivos analisados: {scanned_files}",
        "",
        "## Resumo",
        "",
        f"- Critical: {summary.get('critical', 0)}",
        f"- High: {summary.get('high', 0)}",
        f"- Medium: {summary.get('medium', 0)}",
        f"- Low: {summary.get('low', 0)}",
        "",
        "## Achados",
        "",
    ]
    if not findings:
        lines.append("Nenhum achado identificado no baseline atual.")
    else:
        for finding in findings:
            lines.extend(
                [
                    f"### {finding.rule_id} — {finding.severity.upper()}",
                    "",
                    f"- Arquivo: `{finding.path}:{finding.line}`",
                    f"- Evidência: `{finding.evidence}`",
                    f"- Recomendação: {finding.recommendation}",
                    "",
                ]
            )
    (output_dir / "security-baseline-report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida baseline de segurança do ReqSys.")
    parser.add_argument("--root", default=str(ROOT_DEFAULT), help="Raiz do repositório.")
    parser.add_argument("--output-dir", default="artifacts/security-baseline", help="Diretório de saída dos relatórios.")
    parser.add_argument("--strict", action="store_true", help="Falha o processo quando houver achado crítico.")
    parser.add_argument("--scope", choices={"all", "changed"}, default="all", help="Escopo de varredura: repositório completo ou apenas arquivos alterados.")
    parser.add_argument("--changed-files", default=None, help="Arquivo texto com paths alterados, um por linha, relativo à raiz do repositório.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    output_dir = (root / args.output_dir).resolve()
    include_paths: set[str] | None = None

    if args.scope == "changed":
        if not args.changed_files:
            raise SystemExit("--changed-files é obrigatório quando --scope=changed")
        include_paths = load_changed_file_paths((root / args.changed_files).resolve())

    scanned_files = len(list(iter_files(root, include_paths=include_paths)))
    findings: list[Finding] = []

    scan_env_files(root, findings, include_paths=include_paths)
    scan_lines(root, findings, include_paths=include_paths)
    write_reports(findings, root, output_dir, args.scope, scanned_files)

    summary = summarize(findings)
    if args.strict and summary.get("critical", 0) > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
