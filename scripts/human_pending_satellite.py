#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any

MARKER = "reqsys-human-pending-satellite"

HUMAN_PATTERNS: dict[str, tuple[str, ...]] = {
    "approval_review": ("aprovação obrigatória", "approval required", "review obrigatória", "review required", "aprovação humana"),
    "merge_decision": ("decisão de merge", "merge decision", "human merge", "merge manual"),
    "conflict_choice": ("escolha humana", "decisão humana", "human choice"),
    "environment_approval": ("environment approval", "deployment approval", "aprovação de environment", "aprovação de deployment"),
    "secret_variable": ("secret ausente", "secrets ausentes", "missing secret", "variável ausente", "missing variable", "credencial externa", "external credential"),
    "permission": ("permissão github", "permissão fly", "permissão entra", "missing permission", "sem permissão", "branch protection", "protected branch"),
    "dns_domain": ("dns manual", "configurar dns", "dns externo", "external dns", "domínio externo", "domain ownership"),
    "billing_limit": ("billing", "quota exceeded", "limite de conta", "account limit", "payment required"),
    "operational_acceptance": ("aceite operacional", "operational acceptance", "aceite humano", "human acceptance"),
    "production_confirmation": ("confirmação de produção", "production confirmation", "autorizar produção", "autorizar producao", "prod approval"),
    "architecture_decision": ("decisão arquitetural", "architecture decision", "adr approval", "decisão de arquitetura"),
    "real_external_evidence": ("corpus real", "documento real", "documentos reais", "mfa real", "contrato real", "evidência real", "evidencia real", "revisão humana", "revisao humana", "sign-off", "assinatura formal"),
}

HUMAN_INTENT_PATTERNS = (
    "humano:", "ação humana", "acao humana", "human action", "humana única", "humana unica",
    "blueprint humano", "aprovação humana", "revisão humana", "revisao humana", "pessoa autorizada",
    "responsável", "responsavel", "não pode fabricar", "nao pode fabricar", "não automatizável", "nao automatizavel",
)

TECHNICAL_ONLY_PATTERNS = (
    "ci vermelho", "ci failed", "codeql", "lint", "unit test", "teste unitário", "teste unitario",
    "build failed", "compilation", "compilação", "compilacao", "bug", "falha técnica", "falha tecnica",
    "router", "404", "500", "stack trace", "traceback",
)

APPROVAL_PATTERNS = (
    r"\baprovo\b", r"\bautorizo\b", r"\bapproved\b", r"\bauthorized\b",
)

@dataclass
class Finding:
    issue_number: int
    title: str
    url: str
    categories: list[str]
    decision: str
    reason: str
    impact: str
    environment: str
    evidence: str
    risk: str
    suggested_deadline: str
    automatable_after: str
    action_text: str
    approval_references: list[str]
    signature: str


def norm(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").lower()).strip()


def classify(title: str, body: str) -> list[str]:
    text = norm(f"{title}\n{body}")
    categories = [
        category
        for category, patterns in HUMAN_PATTERNS.items()
        if any(pattern in text for pattern in patterns)
    ]
    if not categories:
        return []

    explicit_human_intent = any(pattern in text for pattern in HUMAN_INTENT_PATTERNS)
    strong_external = any(category in categories for category in {
        "real_external_evidence", "environment_approval", "production_confirmation",
        "architecture_decision", "billing_limit", "dns_domain",
    })
    technical_context = any(pattern in text for pattern in TECHNICAL_ONLY_PATTERNS)

    # A technical issue that merely mentions permissions/secrets must stay with the Coordinator.
    if technical_context and not explicit_human_intent and not strong_external:
        return []

    # Generic mentions are insufficient without explicit human intent or a strong external dependency.
    if not explicit_human_intent and not strong_external:
        return []

    return sorted(set(categories))


def explicit_approval(comment: dict[str, Any]) -> bool:
    body = norm(comment.get("body", ""))
    association = (comment.get("author_association") or "").upper()
    if association not in {"OWNER", "MEMBER", "COLLABORATOR"}:
        return False
    return any(re.search(pattern, body, re.IGNORECASE) for pattern in APPROVAL_PATTERNS)


def approval_refs(comments: list[dict[str, Any]]) -> list[str]:
    refs = []
    for comment in comments:
        if explicit_approval(comment):
            url = comment.get("html_url")
            if url:
                refs.append(url)
    return sorted(set(refs))


def build_finding(issue: dict[str, Any], comments: list[dict[str, Any]], categories: list[str]) -> Finding:
    number = int(issue["number"])
    title = issue.get("title", "")
    raw_body = issue.get("body", "") or ""
    url = issue.get("html_url", "")
    refs = approval_refs(comments)
    body = norm(raw_body)

    external = "real_external_evidence" in categories
    prod = "production_confirmation" in categories or "prod" in body or "produção" in body or "producao" in body

    decision = "Fornecer a evidência/decisão humana real indicada na issue e registrar sua referência verificável."
    reason = "A etapa exige manifestação, credencial, permissão ou evidência externa que o software não pode fabricar nem inferir com segurança."
    impact = "O fluxo permanece bloqueado apenas no ponto governado que depende dessa ação humana."
    environment = "PROD" if prod else "Governança/ambiente indicado na issue"
    evidence = url
    risk = "alto" if prod or external else "médio"
    deadline = "antes da próxima promoção/deploy dependente desta pendência"
    automatable = "Sim. Após a evidência existir, captura de metadados, validação, reconciliação e gates podem ser automáticos."
    action = (
        "Execute a ação humana descrita na issue e registre somente a referência verificável. "
        "Não inclua segredo, dado pessoal, conteúdo bruto ou evidência fictícia."
    )
    if refs:
        decision = "A autorização textual já existe; falta apenas comprovar o fato externo específico exigido pela issue."
        reason = "Aprovação humana foi capturada, mas aprovação não substitui documento, corpus, MFA, contrato, permissão ou efeito externo real."
        evidence = refs[-1]

    raw_signature = json.dumps({
        "n": number,
        "title": title,
        "body_sha256": hashlib.sha256(raw_body.encode("utf-8")).hexdigest(),
        "categories": sorted(categories),
        "refs": refs,
    }, sort_keys=True, ensure_ascii=False)
    signature = hashlib.sha256(raw_signature.encode("utf-8")).hexdigest()[:16]

    return Finding(
        issue_number=number,
        title=title,
        url=url,
        categories=sorted(categories),
        decision=decision,
        reason=reason,
        impact=impact,
        environment=environment,
        evidence=evidence,
        risk=risk,
        suggested_deadline=deadline,
        automatable_after=automatable,
        action_text=action,
        approval_references=refs,
        signature=signature,
    )


class GitHub:
    def __init__(self, token: str, repo: str) -> None:
        self.token = token
        self.repo = repo
        self.base = "https://api.github.com"

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.base + path,
            method=method,
            data=data,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "reqsys-human-pending-satellite",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else None

    def open_issues(self) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        page = 1
        while page <= 10:
            batch = self.request("GET", f"/repos/{self.repo}/issues?state=open&per_page=100&page={page}")
            if not batch:
                break
            issues.extend(item for item in batch if "pull_request" not in item)
            if len(batch) < 100:
                break
            page += 1
        return issues

    def comments(self, issue_number: int) -> list[dict[str, Any]]:
        comments: list[dict[str, Any]] = []
        page = 1
        while page <= 10:
            batch = self.request("GET", f"/repos/{self.repo}/issues/{issue_number}/comments?per_page=100&page={page}") or []
            comments.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return comments

    def comment(self, issue_number: int, body: str) -> None:
        self.request("POST", f"/repos/{self.repo}/issues/{issue_number}/comments", {"body": body})


def render_comment(f: Finding) -> str:
    approvals = "\n".join(f"- {ref}" for ref in f.approval_references) or "- nenhuma autorização explícita capturada"
    return f"""<!-- {MARKER}:issue={f.issue_number}:signature={f.signature} -->
## Pendência humana indispensável — captura automática

- **Decisão exata necessária:** {f.decision}
- **Motivo de não automatização:** {f.reason}
- **Impacto:** {f.impact}
- **Ambiente:** {f.environment}
- **Evidência/link indispensável:** {f.evidence}
- **Risco:** {f.risk}
- **Prazo sugerido:** {f.suggested_deadline}
- **Possibilidade de automatizar depois:** {f.automatable_after}

### Autorizações já capturadas
{approvals}

### Texto objetivo da ação
> {f.action_text}

Esta rotina não considera aprovação textual como prova de fatos externos inexistentes e não cria evidência, credencial, contrato, MFA, corpus, assinatura ou aceite fictício.
"""


def already_notified(comments: list[dict[str, Any]], finding: Finding) -> bool:
    marker = f"<!-- {MARKER}:issue={finding.issue_number}:signature={finding.signature} -->"
    return any(marker in (comment.get("body") or "") for comment in comments)


def run(token: str, repo: str, dry_run: bool, output: str) -> int:
    gh = GitHub(token, repo)
    findings: list[Finding] = []
    notifications = 0
    for issue in gh.open_issues():
        categories = classify(issue.get("title", ""), issue.get("body", ""))
        if not categories:
            continue
        comments = gh.comments(int(issue["number"]))
        finding = build_finding(issue, comments, categories)
        findings.append(finding)
        if not already_notified(comments, finding):
            if not dry_run:
                gh.comment(finding.issue_number, render_comment(finding))
            notifications += 1

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository": repo,
        "dry_run": dry_run,
        "human_findings": [asdict(item) for item in findings],
        "notification_count": notifications,
    }
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    with open(output, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    print(json.dumps({"human_findings": len(findings), "notifications": notifications}, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", default="artifacts/human-pending-satellite/evidence.json")
    args = parser.parse_args()
    if not args.repo or not args.token:
        print("repo/token required", file=sys.stderr)
        return 2
    return run(args.token, args.repo, args.dry_run, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
