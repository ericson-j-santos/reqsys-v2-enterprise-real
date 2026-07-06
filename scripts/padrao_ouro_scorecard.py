#!/usr/bin/env python3
"""Scorecard executivo de maturidade Padrão Ouro do ReqSys.

Consolida um artifact de auditoria de produção em visão executiva por domínio,
com semáforo, percentual, riscos e próximo incremento recomendado. O script é
somente-leitura: não consulta ambientes, não expõe segredos e não altera estado.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_INPUT = "artifacts/prod-readiness-audit.json"
DEFAULT_OUTPUT = "artifacts/padrao-ouro-scorecard.json"
DEFAULT_MARKDOWN_OUTPUT = "artifacts/padrao-ouro-scorecard.md"

STATUS_POINTS = {
    "ok": 100,
    "recommended": 85,
    "manual": 65,
    "action_required": 50,
    "blocked": 0,
}

DOMAIN_WEIGHTS = {
    "security": 20,
    "auth_azure": 15,
    "runtime": 15,
    "secrets": 15,
    "governance": 15,
    "dns": 5,
    "observability": 5,
    "documentation": 5,
    "user_experience": 5,
}

DOMAIN_ALIASES = {
    "auth": "auth_azure",
    "auth_azure": "auth_azure",
    "security": "security",
    "runtime": "runtime",
    "secrets": "secrets",
    "governance": "governance",
    "dns": "dns",
    "observability": "observability",
    "documentation": "documentation",
    "docs": "documentation",
    "ux": "user_experience",
    "user_experience": "user_experience",
}

MANDATORY_DOMAINS = {
    "security",
    "auth_azure",
    "runtime",
    "secrets",
    "governance",
}

NEXT_ACTIONS = {
    "blocked": "corrigir bloqueadores antes de qualquer promoção para produção",
    "action_required": "executar correções objetivas e anexar evidência automatizada",
    "manual": "registrar evidência humana com responsável, data, decisão e rollback",
    "recommended": "converter recomendação em controle automatizado quando houver custo-benefício",
    "ok": "manter monitoramento e evidência viva",
}


@dataclass(frozen=True)
class DomainScore:
    domain: str
    status: str
    score: int
    weight: int
    checks_total: int
    checks_ok: int
    checks_blocked: int
    checks_action_required: int
    human_pending: int
    next_action: str


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_domain(value: str | None) -> str:
    key = str(value or "governance").strip().lower()
    return DOMAIN_ALIASES.get(key, key or "governance")


def normalize_status(value: str | None) -> str:
    status = str(value or "manual").strip().lower()
    return status if status in STATUS_POINTS else "manual"


def status_from_score(score: int) -> str:
    if score >= 95:
        return "ready"
    if score >= 80:
        return "controlled"
    if score >= 60:
        return "attention"
    return "blocked"


def domain_status(checks: list[dict[str, Any]]) -> str:
    statuses = {normalize_status(item.get("status")) for item in checks}
    if "blocked" in statuses:
        return "blocked"
    if "action_required" in statuses:
        return "action_required"
    if "manual" in statuses:
        return "manual"
    if "recommended" in statuses:
        return "recommended"
    return "ok"


def calculate_domain_scores(checks: list[dict[str, Any]]) -> list[DomainScore]:
    by_domain: dict[str, list[dict[str, Any]]] = {domain: [] for domain in DOMAIN_WEIGHTS}
    for check in checks:
        by_domain.setdefault(normalize_domain(check.get("area")), []).append(check)

    scores: list[DomainScore] = []
    for domain, weight in DOMAIN_WEIGHTS.items():
        domain_checks = by_domain.get(domain, [])
        if not domain_checks:
            score = 65 if domain not in MANDATORY_DOMAINS else 50
            status = "manual" if domain not in MANDATORY_DOMAINS else "action_required"
            scores.append(DomainScore(
                domain=domain,
                status=status,
                score=score,
                weight=weight,
                checks_total=0,
                checks_ok=0,
                checks_blocked=0,
                checks_action_required=1 if domain in MANDATORY_DOMAINS else 0,
                human_pending=1,
                next_action="criar check automatizado para evidenciar este domínio",
            ))
            continue

        status = domain_status(domain_checks)
        points = [STATUS_POINTS[normalize_status(item.get("status"))] for item in domain_checks]
        score = round(sum(points) / len(points))
        scores.append(DomainScore(
            domain=domain,
            status=status,
            score=score,
            weight=weight,
            checks_total=len(domain_checks),
            checks_ok=sum(1 for item in domain_checks if normalize_status(item.get("status")) == "ok"),
            checks_blocked=sum(1 for item in domain_checks if normalize_status(item.get("status")) == "blocked"),
            checks_action_required=sum(
                1 for item in domain_checks if normalize_status(item.get("status")) in {"action_required", "manual"}
            ),
            human_pending=sum(1 for item in domain_checks if bool(item.get("human_required"))),
            next_action=NEXT_ACTIONS[status],
        ))
    return scores


def calculate_weighted_score(scores: list[DomainScore]) -> int:
    total_weight = sum(item.weight for item in scores)
    weighted = sum(item.score * item.weight for item in scores)
    return round(weighted / total_weight) if total_weight else 0


def build_scorecard(audit: dict[str, Any]) -> dict[str, Any]:
    checks = audit.get("checks") if isinstance(audit.get("checks"), list) else []
    domain_scores = calculate_domain_scores(checks)
    maturity_percent = calculate_weighted_score(domain_scores)
    blocked_domains = [item.domain for item in domain_scores if item.status == "blocked"]
    attention_domains = [
        item.domain for item in domain_scores if item.status in {"action_required", "manual"}
    ]
    ready_domains = [item.domain for item in domain_scores if item.score >= 95]
    status = status_from_score(maturity_percent)

    return {
        "schema_version": "1.0.0",
        "source": "padrao-ouro-scorecard",
        "generated_at": now(),
        "input_source": audit.get("source"),
        "input_validated_at": audit.get("validated_at"),
        "status": status,
        "maturity_percent": maturity_percent,
        "blocked_domains": blocked_domains,
        "attention_domains": attention_domains,
        "ready_domains": ready_domains,
        "risk": {
            "level": "high" if blocked_domains else "medium" if attention_domains else "low",
            "blocked_count": len(blocked_domains),
            "attention_count": len(attention_domains),
            "confidence": "medium" if any(item.checks_total == 0 for item in domain_scores) else "high",
        },
        "domains": [asdict(item) for item in domain_scores],
        "recommended_next_increment": next_increment(domain_scores),
    }


def next_increment(scores: list[DomainScore]) -> dict[str, Any]:
    ordered = sorted(scores, key=lambda item: (item.score, -item.weight, item.domain))
    target = ordered[0] if ordered else None
    if target is None:
        return {"domain": "governance", "action": "criar baseline de checks padrão ouro"}
    return {
        "domain": target.domain,
        "score": target.score,
        "status": target.status,
        "action": target.next_action,
    }


def write_markdown(scorecard: dict[str, Any], path: Path) -> None:
    icons = {
        "ready": "🟢",
        "controlled": "🟢",
        "attention": "🟡",
        "blocked": "🔴",
        "ok": "🟢",
        "recommended": "🟢",
        "manual": "🟡",
        "action_required": "🟡",
    }
    lines = [
        "# Scorecard Executivo — ReqSys Padrão Ouro",
        "",
        f"Status: **{icons.get(scorecard['status'], '•')} {scorecard['status']}**",
        f"Maturidade: **{scorecard['maturity_percent']}%**",
        f"Risco: **{scorecard['risk']['level']}** · Confiança: **{scorecard['risk']['confidence']}**",
        f"Gerado em: `{scorecard['generated_at']}`",
        "",
        "## Domínios",
        "",
        "| Domínio | Status | Score | Peso | Checks | Pendências humanas | Próxima ação |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for item in scorecard["domains"]:
        lines.append(
            f"| `{item['domain']}` | {icons.get(item['status'], '•')} {item['status']} | "
            f"{item['score']}% | {item['weight']} | {item['checks_total']} | "
            f"{item['human_pending']} | {item['next_action']} |"
        )
    lines.extend([
        "",
        "## Próximo incremento recomendado",
        "",
        f"- Domínio: `{scorecard['recommended_next_increment']['domain']}`",
        f"- Ação: {scorecard['recommended_next_increment']['action']}",
        "",
        "## Critério de pronto para produção padrão ouro",
        "",
        "- Nenhum domínio bloqueado.",
        "- Domínios obrigatórios com score >= 95%.",
        "- Evidência humana registrada quando automação não puder comprovar o controle.",
        "- Artifact JSON versionado como fonte primária para dashboards e auditoria.",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Arquivo de entrada não encontrado: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"JSON inválido em {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"JSON de entrada deve ser um objeto: {path}")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gera scorecard executivo Padrão Ouro do ReqSys")
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    audit = load_json(Path(args.input))
    scorecard = build_scorecard(audit)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(scorecard, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.markdown_output:
        markdown = Path(args.markdown_output)
        markdown.parent.mkdir(parents=True, exist_ok=True)
        write_markdown(scorecard, markdown)

    print(
        f"padrao_ouro_scorecard={scorecard['status']} "
        f"maturity={scorecard['maturity_percent']} "
        f"risk={scorecard['risk']['level']} "
        f"output={output}"
    )
    return 1 if args.strict and scorecard["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
