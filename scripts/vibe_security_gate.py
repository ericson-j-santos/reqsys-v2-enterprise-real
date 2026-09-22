#!/usr/bin/env python3
"""Gate determinístico dos 12 riscos de segurança de vibe coding.

O gate foi desenhado para CI offline/read-only. Ele bloqueia somente sinais
estáticos de alta confiança e classifica riscos contextuais como
``review_required``. Ausência de sinal textual nunca é reportada como prova
de segurança.
"""
from __future__ import annotations

import argparse
import json
import re
import tempfile
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
EXCLUDED_PREFIXES = ("tests/", "backend/tests/", "docs/", ".sdd/")
EXCLUDED_FILES = {"scripts/vibe_security_gate.py"}
TEXT_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".vue", ".mjs", ".cjs"}


@dataclass(frozen=True)
class RiskDefinition:
    risk_id: str
    title: str
    default_enforcement: str
    limitation: str


@dataclass(frozen=True)
class Finding:
    risk_id: str
    severity: str
    enforcement: str
    path: str
    line: int
    evidence: str
    recommendation: str


RISK_DEFINITIONS = (
    RiskDefinition("01", "Segredos no frontend", "block", "O gate identifica exposição provável por nomes públicos; Gitleaks e inspeção do bundle continuam necessários."),
    RiskDefinition("02", "Entradas sem validação", "review", "Validação de negócio e schema precisa ser comprovada por testes positivos e negativos."),
    RiskDefinition("03", "SQL injection", "block", "O gate bloqueia construção SQL dinâmica de alta confiança; ORMs/raw queries exigem revisão adicional."),
    RiskDefinition("04", "Prompt injection", "review", "Prompt injection não é resolvida por prompt de sistema; autorização de ferramenta precisa ser comprovada fora do modelo."),
    RiskDefinition("05", "Cross-site scripting (XSS)", "block", "Sinks HTML brutos são bloqueados quando não há sanitizador explícito no arquivo; contexto de saída ainda exige teste de navegador."),
    RiskDefinition("06", "IDOR e BOLA", "review", "Autorização em nível de objeto/tenant é contextual e requer teste com identidades distintas."),
    RiskDefinition("07", "SSRF", "review", "Destino dinâmico de requisição requer allowlist, validação DNS/rede e teste com mocks; regex não prova explorabilidade."),
    RiskDefinition("08", "Senhas em texto puro", "block", "Hashes fracos são bloqueados; persistência e parâmetros de Argon2id/bcrypt precisam de validação contextual."),
    RiskDefinition("09", "Abuso de requisições / DoS / DDoS", "review", "Rate limit na aplicação não substitui proteção de borda, limites de payload e armazenamento compartilhado."),
    RiskDefinition("10", "Enumeração e rotas administrativas", "review", "Uma rota administrativa pode estar protegida por middleware global; autorização precisa ser comprovada por matriz de acesso."),
    RiskDefinition("11", "Bots em login e cadastro", "review", "CAPTCHA é apenas uma camada; token, origem, ação e limites precisam ser validados no backend."),
    RiskDefinition("12", "Mensagens de erro que vazam dados", "block", "O gate bloqueia retorno explícito de exceções; logs e headers ainda precisam de testes de regressão."),
)

FRONTEND_SECRET = re.compile(r"\b(?:VITE|NEXT_PUBLIC|REACT_APP)_[A-Z0-9_]*(?:SECRET|TOKEN|PASSWORD|PRIVATE|API_KEY|ACCESS_KEY)\b")
SQL_DYNAMIC = re.compile(
    r"""(?ix)
    (?:
      (?:execute|executemany|raw|query)\s*\(\s*f?["'][^"']*(?:select|insert|update|delete)[^"']*\{
      |
      (?:execute|executemany|raw|query)\s*\(\s*["'][^"']*(?:select|insert|update|delete)[^"']*["']\s*\+
      |
      \$queryRawUnsafe\s*\(
    )
    """
)
RAW_HTML = re.compile(r"(?:\.innerHTML\s*=|dangerouslySetInnerHTML|v-html\s*=)")
INSECURE_PASSWORD_HASH = re.compile(r"(?i)(?:hashlib\.)?(?:md5|sha1|sha256)\s*\(\s*(?:password|senha)\b")
ERROR_LEAK = re.compile(
    r"""(?ix)
    (?:
      detail\s*=\s*str\s*\(\s*(?:exc|err|error|exception)\s*\)
      |
      ["']error["']\s*:\s*str\s*\(\s*(?:exc|err|error|exception)\s*\)
      |
      \.json\s*\(\s*\{[^}]*["']error["']\s*:\s*(?:err|error|exc)\.message
    )
    """
)
RAW_BODY = re.compile(r"(?i)(?:\*\*\s*(?:req\.body|payload)|Object\.assign\s*\([^,]+,\s*req\.body|\.update\s*\(\s*req\.body)")
AI_TOOL_MARKER = re.compile(r"(?i)(tool_calls|function_call|modelOutput|model_output|invoke_tool|execute_tool|agent\.invoke)")
AUTH_MARKER = re.compile(r"(?i)(owner[_-]?id|tenant[_-]?id|session\.user|req\.user|current_user|authorize|permission|require_.*(?:role|admin)|rbac)")
OBJECT_ROUTE_MARKER = re.compile(r"(?i)(?:/\{(?:id|project_id|resource_id|.*_id)\}|where\s*[:=]\s*\{?\s*id\s*[:=]|filter\s*\([^)]*\.id\s*==)")
HTTP_DYNAMIC = re.compile(r"(?i)\b(?:fetch|requests\.(?:get|post|put|patch|delete)|httpx\.(?:get|post|put|patch|delete))\s*\(\s*[A-Za-z_][A-Za-z0-9_.]*")
ALLOWLIST_MARKER = re.compile(r"(?i)(allowlist|allowed_hosts|allowed_urls|trusted_hosts|trusted_destinations|targets\s*=\s*(?:new\s+)?Map)")
PASSWORD_PERSISTENCE = re.compile(r"(?i)(?:password|senha)\s*[:=]\s*(?:password|senha)\b")
AUTH_ENDPOINT = re.compile(r"(?i)(/login\b|/signup\b|/register\b|def\s+(?:login|signup|register)\b|function\s+(?:login|signup|register)\b)")
RATE_LIMIT_MARKER = re.compile(r"(?i)(rate[_-]?limit|throttl|limiter|too many requests|\b429\b)")
ADMIN_ROUTE = re.compile(r"""(?i)(/admin(?:/|['"]|\b)|admin[_-]?(?:route|router|endpoint))""")
ADMIN_AUTH_MARKER = re.compile(r"""(?i)(require_admin|is_admin|role\s*[=!]=?\s*['"]admin|permission|authorize|rbac|Depends\s*\([^)]*admin)""")
BOT_ENDPOINT = re.compile(r"(?i)(/signup\b|/register\b|create[_-]?account|cadastro)")
BOT_CONTROL_MARKER = re.compile(r"(?i)(turnstile|captcha|recaptcha|hcaptcha|rate[_-]?limit|throttl|limiter)")


def normalize_repo_path(value: str) -> str:
    return value.strip().replace("\\", "/").lstrip("./")


def load_changed_file_paths(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {normalize_repo_path(line) for line in path.read_text(encoding="utf-8").splitlines() if normalize_repo_path(line)}


def load_changed_line_map(path: Path) -> dict[str, set[int]]:
    """Carrega linhas adicionadas por arquivo para bloquear somente dívida nova no Pre-PR."""
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("changed-lines deve ser um objeto JSON")
    result: dict[str, set[int]] = {}
    for raw_path, raw_lines in payload.items():
        normalized = normalize_repo_path(str(raw_path))
        if not normalized or not isinstance(raw_lines, list):
            continue
        lines: set[int] = set()
        for item in raw_lines:
            try:
                line = int(item)
            except (TypeError, ValueError):
                continue
            if line > 0:
                lines.add(line)
        result[normalized] = lines
    return result


def is_ignored(relative: Path) -> bool:
    normalized = relative.as_posix()
    if normalized in EXCLUDED_FILES or normalized.startswith(EXCLUDED_PREFIXES):
        return True
    return bool(set(relative.parts).intersection(IGNORED_DIRS))


def iter_files(root: Path, include_paths: set[str] | None = None) -> Iterable[Path]:
    if include_paths is not None:
        for rel in sorted(include_paths):
            path = (root / rel).resolve()
            try:
                relative = path.relative_to(root)
            except ValueError:
                continue
            if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS and not is_ignored(relative):
                yield path
        return
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if path.suffix.lower() in TEXT_EXTENSIONS and not is_ignored(relative):
            yield path


def compact(line: str) -> str:
    value = line.strip()
    value = re.sub(r"(?i)(authorization\s*[:=]\s*)(\S+)", r"\1[REDACTED]", value)
    value = re.sub(r"(?i)((?:secret|token|password|senha|api[_-]?key)\s*[:=]\s*)(\S+)", r"\1[REDACTED]", value)
    return value[:220]


def line_of(content: str, offset: int) -> tuple[int, str]:
    lines = content.splitlines()
    line = content.count("\n", 0, offset) + 1
    text = lines[line - 1] if lines else ""
    return line, text


def add(findings: list[Finding], risk_id: str, severity: str, enforcement: str, path: Path, root: Path, content: str, match: re.Match[str], recommendation: str) -> None:
    line_no, line_text = line_of(content, match.start())
    findings.append(Finding(risk_id, severity, enforcement, path.relative_to(root).as_posix(), line_no, compact(line_text), recommendation))


def scan_file(path: Path, root: Path) -> list[Finding]:
    content = path.read_text(encoding="utf-8", errors="replace")
    relative = path.relative_to(root).as_posix()
    findings: list[Finding] = []

    if relative.startswith(("frontend/", "frontend-angular/", "frontend-vuetify/")):
        for match in FRONTEND_SECRET.finditer(content):
            add(findings, "01", "critical", "block", path, root, content, match, "Mover segredo ao backend/secret store e expor ao navegador somente configuração pública necessária.")

    if RAW_BODY.search(content):
        match = RAW_BODY.search(content)
        assert match is not None
        add(findings, "02", "high", "review", path, root, content, match, "Comprovar schema estrito no servidor, rejeição de campos extras e testes de entrada inválida/válida.")

    for match in SQL_DYNAMIC.finditer(content):
        add(findings, "03", "critical", "block", path, root, content, match, "Substituir SQL dinâmico por parâmetros do driver/ORM e adicionar teste de regressão.")

    if AI_TOOL_MARKER.search(content) and not AUTH_MARKER.search(content):
        match = AI_TOOL_MARKER.search(content)
        assert match is not None
        add(findings, "04", "high", "review", path, root, content, match, "Comprovar autorização de ferramenta no backend com identidade da sessão, escopo mínimo e teste de prompt injection.")

    sanitizer_present = bool(re.search(r"(?i)(DOMPurify\.sanitize|sanitizeHtml|sanitize_html|bleach\.clean)", content))
    for match in RAW_HTML.finditer(content):
        add(
            findings,
            "05",
            "critical" if not sanitizer_present else "high",
            "block" if not sanitizer_present else "review",
            path,
            root,
            content,
            match,
            "Evitar HTML bruto; quando necessário, sanitizar com biblioteca mantida e validar em teste de navegador.",
        )

    if OBJECT_ROUTE_MARKER.search(content) and not AUTH_MARKER.search(content):
        match = OBJECT_ROUTE_MARKER.search(content)
        assert match is not None
        add(findings, "06", "high", "review", path, root, content, match, "Comprovar filtro por identidade/tenant e teste conta A versus recurso da conta B.")

    if HTTP_DYNAMIC.search(content) and not ALLOWLIST_MARKER.search(content):
        match = HTTP_DYNAMIC.search(content)
        assert match is not None
        add(findings, "07", "high", "review", path, root, content, match, "Restringir destinos no servidor, bloquear redirecionamentos e testar loopback/redes privadas com mocks.")

    for match in INSECURE_PASSWORD_HASH.finditer(content):
        add(findings, "08", "critical", "block", path, root, content, match, "Usar provedor de identidade ou hash de senha apropriado, como Argon2id, com salt e custo configurado.")
    if PASSWORD_PERSISTENCE.search(content) and not re.search(r"(?i)(password_hash|senha_hash|argon2|bcrypt|scrypt)", content):
        match = PASSWORD_PERSISTENCE.search(content)
        assert match is not None
        add(findings, "08", "high", "review", path, root, content, match, "Comprovar que somente hash de senha é persistido e que texto puro não aparece em logs/respostas.")

    if AUTH_ENDPOINT.search(content) and not RATE_LIMIT_MARKER.search(content):
        match = AUTH_ENDPOINT.search(content)
        assert match is not None
        add(findings, "09", "medium", "review", path, root, content, match, "Comprovar rate limit por conta/IP, limites de payload/timeout e proteção de borda para abuso volumétrico.")

    if ADMIN_ROUTE.search(content) and not ADMIN_AUTH_MARKER.search(content):
        match = ADMIN_ROUTE.search(content)
        assert match is not None
        add(findings, "10", "high", "review", path, root, content, match, "Comprovar autenticação/autorização server-side com matriz sem sessão, usuário comum e administrador.")

    if BOT_ENDPOINT.search(content) and not BOT_CONTROL_MARKER.search(content):
        match = BOT_ENDPOINT.search(content)
        assert match is not None
        add(findings, "11", "medium", "review", path, root, content, match, "Comprovar validação server-side do desafio e controles complementares de tentativa/monitoramento.")

    for match in ERROR_LEAK.finditer(content):
        add(findings, "12", "critical", "block", path, root, content, match, "Retornar mensagem genérica e correlation/request id; manter detalhes apenas em logs sanitizados.")

    return findings


def scan_repository(root: Path, include_paths: set[str] | None = None) -> tuple[list[Finding], int]:
    findings: list[Finding] = []
    files = list(iter_files(root, include_paths=include_paths))
    for path in files:
        findings.extend(scan_file(path, root))
    return findings, len(files)


def filter_blockers_to_changed_lines(
    findings: list[Finding],
    changed_lines: dict[str, set[int]],
) -> list[Finding]:
    """Mantém reviews contextuais, mas bloqueia apenas sinais novos nas linhas adicionadas."""
    return [
        item
        for item in findings
        if item.enforcement != "block" or item.line in changed_lines.get(item.path, set())
    ]


def risk_statuses(findings: list[Finding]) -> list[dict]:
    by_risk: dict[str, list[Finding]] = {risk.risk_id: [] for risk in RISK_DEFINITIONS}
    for finding in findings:
        by_risk.setdefault(finding.risk_id, []).append(finding)
    rows: list[dict] = []
    for risk in RISK_DEFINITIONS:
        items = by_risk.get(risk.risk_id, [])
        if any(item.enforcement == "block" for item in items):
            status = "blocked"
        elif items:
            status = "review_required"
        else:
            status = "no_signal"
        rows.append(
            {
                "risk_id": risk.risk_id,
                "title": risk.title,
                "default_enforcement": risk.default_enforcement,
                "status": status,
                "limitation": risk.limitation,
                "finding_count": len(items),
            }
        )
    return rows


def write_reports(root: Path, output_dir: Path, scope: str, scanned_files: int, findings: list[Finding]) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    blockers = [item for item in findings if item.enforcement == "block"]
    reviews = [item for item in findings if item.enforcement == "review"]
    payload = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "blocked" if blockers else "passed",
        "scan_scope": scope,
        "scanned_files": scanned_files,
        "summary": {
            "blockers": len(blockers),
            "review_required": len(reviews),
            "findings": len(findings),
            "risks_with_signal": len({item.risk_id for item in findings}),
        },
        "risks": risk_statuses(findings),
        "findings": [asdict(item) for item in findings],
        "assurance_note": "Ausência de sinal textual não comprova segurança. Use testes positivos/negativos, evidência de runtime e scanners especializados.",
    }
    (output_dir / "vibe-security-report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Vibe Coding Security — 12 riscos",
        "",
        f"Status do gate: **{payload['status'].upper()}**",
        "",
        f"- Escopo: `{scope}`",
        f"- Arquivos analisados: {scanned_files}",
        f"- Bloqueadores: {len(blockers)}",
        f"- Revisões obrigatórias: {len(reviews)}",
        "",
        "> Ausência de sinal textual não comprova segurança; riscos contextuais permanecem vinculados a testes e evidência de runtime.",
        "",
        "| Risco | Estado | Sinais |",
        "|---|---|---:|",
    ]
    for row in payload["risks"]:
        lines.append(f"| {row['risk_id']} — {row['title']} | `{row['status']}` | {row['finding_count']} |")
    if findings:
        lines.extend(["", "## Achados", ""])
        for finding in findings:
            lines.extend([
                f"### {finding.risk_id} — {finding.severity.upper()} / {finding.enforcement}",
                f"- Arquivo: `{finding.path}:{finding.line}`",
                f"- Evidência: `{finding.evidence}`",
                f"- Correção/validação: {finding.recommendation}",
                "",
            ])
    (output_dir / "vibe-security-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


def self_test_negative() -> bool:
    with tempfile.TemporaryDirectory(prefix="reqsys-vibe-security-negative-") as tmp:
        root = Path(tmp)
        target = root / "frontend" / "src" / "config.js"
        target.parent.mkdir(parents=True)
        target.write_text("const key = import.meta.env.VITE_PRIVATE_API_KEY;\n", encoding="utf-8")
        findings, _ = scan_repository(root)
        return any(item.risk_id == "01" and item.enforcement == "block" for item in findings)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Valida os 12 riscos de segurança de vibe coding com sinais determinísticos.")
    parser.add_argument("--root", default=str(ROOT_DEFAULT))
    parser.add_argument("--output-dir", default="artifacts/security-baseline/vibe-security")
    parser.add_argument("--strict", action="store_true", help="Falha quando houver achado com enforcement=block.")
    parser.add_argument("--scope", choices={"all", "changed"}, default="all")
    parser.add_argument("--changed-files", default=None)
    parser.add_argument(
        "--changed-lines",
        default=None,
        help="JSON opcional path -> linhas adicionadas; em scope=changed limita blockers à dívida nova.",
    )
    parser.add_argument("--self-test-negative", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test_negative:
        ok = self_test_negative()
        print(json.dumps({"self_test_negative": ok}))
        return 0 if ok else 1

    root = Path(args.root).resolve()
    include_paths: set[str] | None = None
    changed_lines: dict[str, set[int]] | None = None
    if args.scope == "changed":
        if not args.changed_files:
            raise SystemExit("--changed-files é obrigatório quando --scope=changed")
        include_paths = load_changed_file_paths((root / args.changed_files).resolve())
        if args.changed_lines:
            try:
                changed_lines = load_changed_line_map((root / args.changed_lines).resolve())
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                raise SystemExit(f"changed-lines inválido: {exc}") from exc

    findings, scanned_files = scan_repository(root, include_paths=include_paths)
    if changed_lines is not None:
        findings = filter_blockers_to_changed_lines(findings, changed_lines)
    payload = write_reports(root, (root / args.output_dir).resolve(), args.scope, scanned_files, findings)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.strict and payload["summary"]["blockers"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
