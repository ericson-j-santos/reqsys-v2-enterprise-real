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
DEFER_NONPROD_LABEL = "satellite:defer-nonprod"
PROD_ONLY_LABEL = "scope:prod-only"
OCR_CERT_ONLY_LABEL = "scope:ocr-certification-only"
VALID_SCOPES = {"nonprod", "prod", "ocr-certification"}

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

# Pendências conhecidas em que o texto histórico da issue já não representa
# necessariamente o gate humano vigente. A automação continua dinâmica; estes
# overrides só tornam a notificação residual precisa quando a remediação
# automática terminou bloqueada.
HUMAN_GATE_OVERRIDES: dict[int, dict[str, str]] = {
    1130: {
        "decision": "Aprovar a permissão Workflows: read/write da GitHub App reqsys-stack-rebase na instalação restrita ao ReqSys.",
        "reason": "Alterar permissões de uma GitHub App exige uma conta administradora em sudo mode; a rotina usa token efêmero e não pode autoelevar a própria instalação.",
        "impact": "Sem essa permissão, a promoção governada de arquivos em .github/workflows permanece fail-closed.",
        "environment": "GitHub / repositório ReqSys",
        "risk": "alto",
        "deadline": "antes da próxima promoção governada que altere workflow",
        "automatable": "Sim. Após a aprovação única da permissão, emissão do token efêmero, prova de escrita, limpeza e promoção voltam a ser automáticas.",
        "action": "GitHub admin: aprovar somente Workflows: read/write para a App reqsys-stack-rebase instalada no ReqSys. Não gerar nem colar PAT.",
    },
    1520: {
        "decision": "Disponibilizar a origem SQL corporativa autorizada com TLS confiável, ou materializar a cadeia de confiança aprovada no SQL DEV quando esse for o alvo válido.",
        "reason": "O ReqSys pode descobrir, montar DSN, armazenar no Key Vault e validar automaticamente, mas não pode escolher a fonte corporativa nem emitir/aceitar um certificado não confiável em nome da Infra/Dados.",
        "impact": "Bloqueia a prova real de leitura da fonte Movimento sem permitir fallback inseguro com TrustServerCertificate.",
        "environment": "DEV / origem SQL corporativa",
        "risk": "alto",
        "deadline": "antes do próximo E2E real de Prospecção Movimento",
        "automatable": "Sim. Assim que host/banco/segredos referenciados e TLS confiável existirem, o bootstrap e a validação são retomados automaticamente.",
        "action": "Infra/Dados: disponibilizar a origem SQL aprovada e TLS confiável; registrar somente referências/nomes de secrets no fluxo governado, sem publicar credenciais.",
    },
    1521: {
        "decision": "Definir a caixa técnica remetente e aprovar Mail.Send de aplicação para a identidade Entra do ReqSys, restrita à caixa autorizada.",
        "reason": "Consentimento administrativo Microsoft 365 e escolha da caixa técnica são atos externos de autoridade; o software não pode conceder a si próprio Mail.Send nem inferir qual mailbox institucional deve representar o serviço.",
        "impact": "Bloqueia somente o envio Graph real; dry-run, fila e adapter continuam automatizados.",
        "environment": "Microsoft 365 / DEV",
        "risk": "alto",
        "deadline": "antes do primeiro envio controlado",
        "automatable": "Sim. Após consentimento e identificação da caixa, readiness, dry-run, envio controlado, correlation_id e validação podem seguir automaticamente.",
        "action": "Administrador M365/Entra: confirmar a mailbox técnica autorizada e conceder Mail.Send Application com escopo mínimo para essa caixa; não enviar segredo pelo GitHub.",
    },
    1532: {
        "decision": "Instalar o pacote Teams DEV já gerado e iniciar a primeira conversa com o bot para materializar a conversationReference.",
        "reason": "A instalação no cliente/usuário e a primeira interação originada por uma pessoa são efeitos externos do Teams; a automação de Azure Bot/Fly não deve fabricar uma conversa de usuário.",
        "impact": "Sem a primeira interação, o gateway não possui conversationReference real para provar o E2E ReqSys ↔ Teams.",
        "environment": "Microsoft Teams / DEV",
        "risk": "médio",
        "deadline": "após o provisionamento automático do bot ficar verde",
        "automatable": "Sim. Depois da primeira conversationReference real, persistência, replay, health/readiness e mensagens subsequentes podem ser automáticos.",
        "action": "No Teams DEV, instalar o pacote publicado pelo workflow Teams Bot DEV Provision e enviar uma mensagem ao bot; não copiar tokens ou segredos.",
    },
    1649: {
        "decision": "Concluir a autenticação delegada Microsoft por device code/MFA quando o E2E Power Platform solicitar consentimento interativo.",
        "reason": "O fluxo atual depende de token delegado para service.flow.microsoft.com/api.powerplatform.com; MFA/consentimento do usuário não pode ser simulado, armazenado como senha ou contornado por credencial de aplicação.",
        "impact": "Bloqueia a evidência funcional real Excel → SQL Server → SharePoint, sem afetar os testes contratuais.",
        "environment": "Power Platform / DEV",
        "risk": "alto",
        "deadline": "na próxima janela de E2E funcional",
        "automatable": "Parcial. O workflow, a espera, a retomada, a coleta de evidência e o replay são automáticos; somente o desafio MFA permanece humano enquanto a arquitetura exigir token delegado.",
        "action": "Quando o workflow exibir o device code Microsoft, concluir o login/MFA na conta autorizada. Não compartilhar código, token ou senha no GitHub.",
    },
}

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


def _label_names(issue: dict[str, Any]) -> set[str]:
    labels: set[str] = set()
    for item in issue.get("labels") or []:
        if isinstance(item, str):
            labels.add(item.strip().lower())
        elif isinstance(item, dict) and item.get("name"):
            labels.add(str(item["name"]).strip().lower())
    return labels


def deferred_scope(issue: dict[str, Any]) -> str | None:
    labels = _label_names(issue)
    if DEFER_NONPROD_LABEL not in labels:
        return None
    if PROD_ONLY_LABEL in labels:
        return "prod"
    if OCR_CERT_ONLY_LABEL in labels:
        return "ocr-certification"
    return None


def should_defer_notification(issue: dict[str, Any], scope: str) -> bool:
    if scope not in VALID_SCOPES:
        raise ValueError(f"scope inválido: {scope}")
    target_scope = deferred_scope(issue)
    return target_scope is not None and target_scope != scope


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

    override = HUMAN_GATE_OVERRIDES.get(number)
    if override:
        decision = override["decision"]
        reason = override["reason"]
        impact = override["impact"]
        environment = override["environment"]
        risk = override["risk"]
        deadline = override["deadline"]
        automatable = override["automatable"]
        action = override["action"]
        if refs:
            evidence = refs[-1]

    raw_signature = json.dumps({
        "n": number,
        "title": title,
        "body_sha256": hashlib.sha256(raw_body.encode("utf-8")).hexdigest(),
        "categories": sorted(categories),
        "refs": refs,
        "override": HUMAN_GATE_OVERRIDES.get(number),
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


def load_auto_remediation_suppression(path: str | None) -> set[int]:
    if not path or not os.path.isfile(path):
        return set()
    try:
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return set()
    return {
        int(item["issue_number"])
        for item in payload.get("results", [])
        if item.get("suppress_human") is True
        and item.get("state") in {"in_progress", "recent_success", "dispatched"}
        and str(item.get("issue_number", "")).isdigit()
    }


def run(
    token: str,
    repo: str,
    dry_run: bool,
    output: str,
    scope: str = "nonprod",
    remediation_file: str | None = None,
) -> int:
    if scope not in VALID_SCOPES:
        raise ValueError(f"scope inválido: {scope}")
    gh = GitHub(token, repo)
    suppressed = load_auto_remediation_suppression(remediation_file)
    findings: list[Finding] = []
    notifications = 0
    for issue in gh.open_issues():
        issue_number = int(issue["number"])
        if issue_number in suppressed:
            continue
        if should_defer_notification(issue, scope):
            continue
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
        "scope": scope,
        "suppressed_by_auto_remediation": sorted(suppressed),
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
    parser.add_argument("--scope", choices=sorted(VALID_SCOPES), default="nonprod")
    parser.add_argument("--remediation-file", default="")
    parser.add_argument("--output", default="artifacts/human-pending-satellite/evidence.json")
    args = parser.parse_args()
    if not args.repo or not args.token:
        print("repo/token required", file=sys.stderr)
        return 2
    return run(
        args.token,
        args.repo,
        args.dry_run,
        args.output,
        args.scope,
        args.remediation_file or None,
    )


if __name__ == "__main__":
    raise SystemExit(main())
