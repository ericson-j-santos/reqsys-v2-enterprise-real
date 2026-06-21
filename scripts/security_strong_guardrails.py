#!/usr/bin/env python3
"""Guardrails fortes de seguranca para CI."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "security-reports"
REPORT_JSON = REPORT_DIR / "security-strong-guardrails.json"
REPORT_MD = REPORT_DIR / "security-strong-guardrails.md"
SCANNER_RELATIVE_PATH = "scripts/security_strong_guardrails.py"

EXCLUDED_DIRS = {".git", ".venv", "venv", "node_modules", "dist", "build", "coverage", "security-reports", "ci-reports"}
TEXT_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".vue", ".json", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".env", ".example", ".md", ".html", ".css", ".sh", ".ps1"}
ALLOWLIST_HINTS = ("example", "exemplo", "sample", "mock", "fixture", "test", "tests", "readme", "changelog", "adr", "docs/", "agents.md")
NON_BLOCKING_RUNTIME_STATUS_FIELDS = ("demo_login_enabled",)

@dataclass(frozen=True)
class Finding:
    severity: str
    category: str
    path: str
    line: int
    rule: str
    recommendation: str


def normalize(value: str) -> str:
    return value.strip().lower().replace('"', "'").replace(" ", "")


def should_skip(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    if rel == SCANNER_RELATIVE_PATH:
        return True
    if path.is_dir():
        return True
    if any(rel == item or rel.startswith(f"{item}/") for item in EXCLUDED_DIRS):
        return True
    return path.suffix.lower() not in TEXT_EXTENSIONS and path.name not in {"Dockerfile", ".env", ".env.example"}


def is_allowed(rel: str) -> bool:
    lowered = rel.lower()
    return any(hint in lowered for hint in ALLOWLIST_HINTS)


def is_non_blocking_status_line(value: str) -> bool:
    return any(field in value for field in NON_BLOCKING_RUNTIME_STATUS_FIELDS)


def classify_line(rel: str, line_number: int, raw_line: str) -> tuple[list[Finding], list[Finding]]:
    critical: list[Finding] = []
    warnings: list[Finding] = []
    value = normalize(raw_line)
    if not value or value.startswith("#") or is_allowed(rel):
        return critical, warnings

    critical_checks = [
        ("AUTH_DISABLED", "auth", ("auth_enabled=false", "enable_auth=false", "vite_enable_auth=false"), "Manter autenticacao obrigatoria; nao versionar flag desligada."),
        ("DEMO_LOGIN_ENABLED", "auth", ("demo_login=true", "enable_demo_login=true", "allow_demo_auth=true"), "Remover login demonstrativo de codigo/configuracao versionada."),
        ("CORS_WILDCARD", "cors", ("cors_origins=*", "cors_origin=*", "allow_origins=['*']"), "Substituir CORS wildcard por origens explicitas por ambiente."),
        ("JWT_VALIDATION_DISABLED", "jwt", ("jwt_verify=false", "validissuer=false", "validaudience=false", "verify_signature=false"), "JWT deve validar assinatura, emissor, audiencia e expiracao."),
        ("TLS_VALIDATION_DISABLED", "tls", ("verify=false", "rejectunauthorized=false", "node_tls_reject_unauthorized=0"), "TLS nao pode ser desabilitado; usar CA bundle corporativo quando necessario."),
        ("ENVIRONMENT_DUMP", "logging", ("print(os.environ", "console.log(process.env", "logger.info(os.environ"), "Nao registrar variaveis de ambiente em log."),
    ]
    for rule, category, tokens, recommendation in critical_checks:
        if rule == "DEMO_LOGIN_ENABLED" and is_non_blocking_status_line(value):
            continue
        if any(token in value for token in tokens):
            critical.append(Finding("critical", category, rel, line_number, rule, recommendation))

    if rel.startswith(".github/workflows/"):
        warning_checks = [
            ("BROAD_WORKFLOW_PERMISSION", "ci-permissions", ("contents:write", "pull-requests:write", "actions:write", "id-token:write"), "Permissoes write exigem justificativa e escopo minimo."),
            ("VERSION_TAGGED_ACTION", "supply-chain", ("uses:actions/checkout@v", "uses:actions/setup-python@v", "uses:actions/upload-artifact@v"), "Avaliar pin por SHA em workflows criticos."),
        ]
        for rule, category, tokens, recommendation in warning_checks:
            if any(token in value for token in tokens):
                warnings.append(Finding("warning", category, rel, line_number, rule, recommendation))

    return critical, warnings


def scan_repository() -> tuple[list[Finding], list[Finding]]:
    critical: list[Finding] = []
    warnings: list[Finding] = []
    for path in sorted(ROOT.rglob("*")):
        if should_skip(path):
            continue
        rel = path.relative_to(ROOT).as_posix()
        content = path.read_text(encoding="utf-8", errors="ignore")
        for line_number, raw_line in enumerate(content.splitlines(), start=1):
            line_critical, line_warnings = classify_line(rel, line_number, raw_line)
            critical.extend(line_critical)
            warnings.extend(line_warnings)
    return critical, warnings


def write_reports(critical: list[Finding], warnings: list[Finding]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    status = "failed" if critical else "passed"
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": "security-strong-guardrails-v1",
        "status": status,
        "critical_count": len(critical),
        "warning_count": len(warnings),
        "critical_findings": [asdict(item) for item in critical],
        "warning_findings": [asdict(item) for item in warnings],
    }
    REPORT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Security Strong Guardrails", "", f"- Status: **{status}**", f"- Criticos: **{len(critical)}**", f"- Alertas: **{len(warnings)}**", "", "## Achados criticos", ""]
    if critical:
        lines += ["| Regra | Categoria | Arquivo | Linha | Recomendacao |", "|---|---|---|---:|---|"]
        for item in critical:
            lines.append(f"| `{item.rule}` | {item.category} | `{item.path}` | {item.line} | {item.recommendation} |")
    else:
        lines.append("Nenhum achado critico bloqueante encontrado.")
    lines += ["", "## Alertas", ""]
    if warnings:
        lines += ["| Regra | Categoria | Arquivo | Linha | Recomendacao |", "|---|---|---|---:|---|"]
        for item in warnings[:100]:
            lines.append(f"| `{item.rule}` | {item.category} | `{item.path}` | {item.line} | {item.recommendation} |")
    else:
        lines.append("Nenhum alerta encontrado.")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    critical, warnings = scan_repository()
    write_reports(critical, warnings)
    print(f"Security Strong Guardrails: {len(critical)} critico(s), {len(warnings)} alerta(s).")
    print(f"Relatorio: {REPORT_MD.relative_to(ROOT)}")
    return 1 if critical else 0

if __name__ == "__main__":
    raise SystemExit(main())
