#!/usr/bin/env python3
"""PR Quality Review deterministico para substituir reviews externos.

Objetivo:
- gerar revisao automatizada de PR sem dependencia de bot externo;
- classificar risco, escopo, arquivos sensiveis e tamanho do diff;
- publicar JSON/Markdown como artifact;
- opcionalmente comentar no PR;
- falhar apenas quando houver risco critico objetivo.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

API_VERSION = "2022-11-28"
DEFAULT_REPORT_DIR = Path("artifacts/pr-quality-review")
CRITICAL_PATHS = (
    ".github/workflows/",
    "infra/",
    "terraform/",
    "k8s/",
    "helm/",
    "backend/app/core/security",
    "backend/app/core/auth",
    "backend/app/services/auth",
)
SENSITIVE_FILENAMES = (
    ".env",
    ".p12",
    ".pfx",
    "id_rsa",
    "private_key",
    "secrets",
    "secret",
    "token",
    "credentials",
)
DOC_EXTENSIONS = {".md", ".mdx", ".txt"}
TEST_HINTS = ("test_", "_test", "/tests/", "spec.", ".spec.")


@dataclass(frozen=True)
class ChangedFile:
    filename: str
    status: str
    additions: int
    deletions: int
    changes: int
    patch: str | None = None

    @property
    def extension(self) -> str:
        return Path(self.filename).suffix.lower()

    @property
    def is_test(self) -> bool:
        lowered = self.filename.lower()
        return any(hint in lowered for hint in TEST_HINTS)

    @property
    def is_doc(self) -> bool:
        return self.extension in DOC_EXTENSIONS or self.filename.lower().startswith("docs/")

    @property
    def is_workflow(self) -> bool:
        return self.filename.startswith(".github/workflows/")

    @property
    def is_sensitive(self) -> bool:
        lowered = self.filename.lower()
        return any(marker in lowered for marker in SENSITIVE_FILENAMES)

    @property
    def is_critical_path(self) -> bool:
        return any(self.filename.startswith(path) for path in CRITICAL_PATHS)


@dataclass(frozen=True)
class PullRequestContext:
    repo: str
    pr_number: str
    title: str
    state: str
    draft: bool
    head_sha: str
    base_ref: str
    html_url: str


@dataclass(frozen=True)
class QualityFinding:
    severity: str
    category: str
    message: str
    evidence: str


def request_json(method: str, url: str, token: str, payload: dict[str, Any] | None = None) -> dict[str, Any] | list[Any]:
    data = None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": "reqsys-pr-quality-review",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:  # noqa: S310 - GitHub API URL controlada
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"GitHub API falhou {exc.code}: {detail}") from exc


def fetch_pr(repo: str, pr_number: str, token: str) -> PullRequestContext:
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    data = request_json("GET", url, token)
    if not isinstance(data, dict):
        raise RuntimeError("Resposta inesperada ao buscar PR")
    return PullRequestContext(
        repo=repo,
        pr_number=pr_number,
        title=str(data.get("title") or ""),
        state=str(data.get("state") or "unknown"),
        draft=bool(data.get("draft")),
        head_sha=str(data.get("head", {}).get("sha") or ""),
        base_ref=str(data.get("base", {}).get("ref") or ""),
        html_url=str(data.get("html_url") or ""),
    )


def fetch_changed_files(repo: str, pr_number: str, token: str) -> list[ChangedFile]:
    files: list[ChangedFile] = []
    page = 1
    while True:
        url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/files?per_page=100&page={page}"
        data = request_json("GET", url, token)
        if not isinstance(data, list):
            raise RuntimeError("Resposta inesperada ao buscar arquivos do PR")
        if not data:
            break
        for item in data:
            files.append(
                ChangedFile(
                    filename=str(item.get("filename") or ""),
                    status=str(item.get("status") or "unknown"),
                    additions=int(item.get("additions") or 0),
                    deletions=int(item.get("deletions") or 0),
                    changes=int(item.get("changes") or 0),
                    patch=item.get("patch"),
                )
            )
        page += 1
    return files


def classify_risk(files: list[ChangedFile], pr: PullRequestContext) -> tuple[str, int, list[QualityFinding]]:
    findings: list[QualityFinding] = []
    total_changes = sum(file.changes for file in files)
    critical_files = [file for file in files if file.is_critical_path]
    sensitive_files = [file for file in files if file.is_sensitive]
    test_files = [file for file in files if file.is_test]
    code_files = [file for file in files if not file.is_doc and not file.is_test]
    workflow_files = [file for file in files if file.is_workflow]

    score = 100

    if sensitive_files:
        score -= 50
        findings.append(
            QualityFinding(
                severity="critical",
                category="seguranca",
                message="Arquivos potencialmente sensiveis foram alterados.",
                evidence=", ".join(file.filename for file in sensitive_files[:10]),
            )
        )

    if workflow_files:
        score -= 20
        findings.append(
            QualityFinding(
                severity="warning",
                category="ci_cd",
                message="Workflows GitHub Actions foram alterados; requer atencao extra.",
                evidence=", ".join(file.filename for file in workflow_files[:10]),
            )
        )

    if critical_files:
        score -= 15
        findings.append(
            QualityFinding(
                severity="warning",
                category="caminho_critico",
                message="Arquivos em caminhos criticos foram alterados.",
                evidence=", ".join(file.filename for file in critical_files[:10]),
            )
        )

    if total_changes > 800:
        score -= 25
        findings.append(
            QualityFinding(
                severity="warning",
                category="tamanho",
                message="PR grande; recomenda-se revisar escopo ou quebrar em PRs menores.",
                evidence=f"{total_changes} linhas alteradas",
            )
        )
    elif total_changes > 300:
        score -= 10
        findings.append(
            QualityFinding(
                severity="info",
                category="tamanho",
                message="PR medio; revisar coerencia de escopo.",
                evidence=f"{total_changes} linhas alteradas",
            )
        )

    if code_files and not test_files:
        score -= 15
        findings.append(
            QualityFinding(
                severity="warning",
                category="testes",
                message="Ha alteracao de codigo sem arquivo de teste no mesmo PR.",
                evidence=f"{len(code_files)} arquivo(s) de codigo; 0 arquivo(s) de teste",
            )
        )

    if pr.draft:
        findings.append(
            QualityFinding(
                severity="info",
                category="estado_pr",
                message="PR esta em draft; comentario automatizado deve ser tratado como diagnostico preliminar.",
                evidence="draft=true",
            )
        )

    score = max(0, min(100, score))
    if any(finding.severity == "critical" for finding in findings):
        severity = "critical"
    elif score < 75 or any(finding.severity == "warning" for finding in findings):
        severity = "warning"
    else:
        severity = "ok"
    return severity, score, findings


def render_markdown(pr: PullRequestContext, files: list[ChangedFile], severity: str, score: int, findings: list[QualityFinding]) -> str:
    total_additions = sum(file.additions for file in files)
    total_deletions = sum(file.deletions for file in files)
    total_changes = sum(file.changes for file in files)
    test_count = sum(1 for file in files if file.is_test)
    doc_count = sum(1 for file in files if file.is_doc)
    workflow_count = sum(1 for file in files if file.is_workflow)
    sensitive_count = sum(1 for file in files if file.is_sensitive)

    indicator = {"ok": "GREEN", "warning": "YELLOW", "critical": "RED"}.get(severity, "UNKNOWN")
    decision = {
        "ok": "PR sem bloqueio objetivo pelo PR Quality Review.",
        "warning": "Revisar pontos de atencao antes do merge.",
        "critical": "Bloquear merge ate tratar achados criticos.",
    }.get(severity, "Investigar resultado desconhecido.")

    lines = [
        "# PR Quality Review",
        "",
        f"**Indicador:** `{indicator}`  ",
        f"**Severidade:** `{severity}`  ",
        f"**Score:** `{score}/100`  ",
        f"**Decisao:** {decision}",
        "",
        "## Contexto",
        "",
        "| Campo | Valor |",
        "|---|---|",
        f"| Repositorio | `{pr.repo}` |",
        f"| PR | `#{pr.pr_number}` |",
        f"| Titulo | `{pr.title}` |",
        f"| Base | `{pr.base_ref}` |",
        f"| Head SHA | `{pr.head_sha}` |",
        f"| Draft | `{str(pr.draft).lower()}` |",
        f"| Gerado em UTC | `{datetime.now(timezone.utc).isoformat()}` |",
        "",
        "## Metricas",
        "",
        "| Arquivos | Adicoes | Remocoes | Mudancas | Testes | Docs | Workflows | Sensiveis |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
        f"| {len(files)} | {total_additions} | {total_deletions} | {total_changes} | {test_count} | {doc_count} | {workflow_count} | {sensitive_count} |",
        "",
        "## Achados",
        "",
    ]

    if not findings:
        lines.append("- Nenhum achado critico ou warning objetivo identificado.")
    else:
        for finding in findings:
            lines.append(
                f"- **{finding.severity.upper()}** `{finding.category}` — {finding.message}  "
                f"Evidencia: `{finding.evidence}`"
            )

    lines.extend(
        [
            "",
            "## Arquivos alterados",
            "",
            "| Arquivo | Status | + | - | Mudancas | Flags |",
            "|---|---|---:|---:|---:|---|",
        ]
    )
    for file in files[:80]:
        flags = []
        if file.is_workflow:
            flags.append("workflow")
        if file.is_critical_path:
            flags.append("critico")
        if file.is_sensitive:
            flags.append("sensivel")
        if file.is_test:
            flags.append("teste")
        if file.is_doc:
            flags.append("doc")
        lines.append(
            f"| `{file.filename}` | `{file.status}` | {file.additions} | {file.deletions} | {file.changes} | `{', '.join(flags) or '-'}` |"
        )

    lines.extend(
        [
            "",
            "## Politica de substituicao do CodeRabbit",
            "",
            "- Sem dependencia de IA externa ou limite de quota.",
            "- Falha apenas para risco critico objetivo.",
            "- Warnings ficam visiveis para decisao humana.",
            "- CI, seguranca e testes continuam sendo fonte de verdade para merge.",
        ]
    )
    return "\n".join(lines) + "\n"


def post_comment(repo: str, pr_number: str, token: str, body: str) -> None:
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    request_json("POST", url, token, {"body": body})


def write_report(report_dir: Path, pr: PullRequestContext, files: list[ChangedFile], severity: str, score: int, findings: list[QualityFinding]) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "pr": asdict(pr),
        "summary": {
            "severity": severity,
            "score": score,
            "decision": "block" if severity == "critical" else "review" if severity == "warning" else "ok",
        },
        "files": [asdict(file) for file in files],
        "findings": [asdict(finding) for finding in findings],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (report_dir / "pr-quality-review.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown = render_markdown(pr, files, severity, score, findings)
    (report_dir / "pr-quality-review.md").write_text(markdown, encoding="utf-8")
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as handle:
            handle.write(markdown)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr-number", required=True)
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR))
    parser.add_argument("--comment", action="store_true")
    args = parser.parse_args()

    report_dir = Path(args.report_dir)
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        fallback_pr = PullRequestContext(args.repo, args.pr_number, "unknown", "unknown", False, "unknown", "unknown", "")
        write_report(
            report_dir,
            fallback_pr,
            [],
            "warning",
            70,
            [QualityFinding("warning", "api", "GITHUB_TOKEN ausente; fallback report-only gerado.", "env:GITHUB_TOKEN")],
        )
        return 0

    try:
        pr = fetch_pr(args.repo, args.pr_number, token)
        files = fetch_changed_files(args.repo, args.pr_number, token)
        severity, score, findings = classify_risk(files, pr)
        write_report(report_dir, pr, files, severity, score, findings)
        if args.comment:
            markdown = (report_dir / "pr-quality-review.md").read_text(encoding="utf-8")
            post_comment(args.repo, args.pr_number, token, markdown)
        return 1 if severity == "critical" else 0
    except Exception as exc:  # noqa: BLE001 - fallback governado precisa capturar falhas operacionais do coletor
        fallback_pr = PullRequestContext(args.repo, args.pr_number, "unresolved", "unknown", False, "unknown", "unknown", "")
        write_report(
            report_dir,
            fallback_pr,
            [],
            "warning",
            70,
            [QualityFinding("warning", "api", "Falha operacional no PR Quality Review; fallback report-only gerado.", str(exc)[:500])],
        )
        print(f"PR Quality Review fallback gerado: {exc}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
