"""Executor Router: classifica uma solicitação no executor responsável.

O roteamento é determinístico e auditável: cada decisão devolve a regra que a
produziu e os termos que dispararam a regra, de modo que um roteamento errado
seja corrigido na regra e não em interpretação caso a caso.

Regra de precedência: bloqueios de identidade/permissão vencem qualquer outra
classificação, porque executá-los automaticamente apenas antecipa a falha de
autenticação para dentro do E2E (ver "Control Plane de identidades").
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

from app.domain.central.models import ExecutorKind, WorkRequestInput


@dataclass(frozen=True)
class RoutingRule:
    rule_id: str
    executor: ExecutorKind
    terms: tuple[str, ...]
    human_reason: str | None = None


@dataclass(frozen=True)
class RoutingDecision:
    executor: ExecutorKind
    rule_id: str
    matched_terms: tuple[str, ...] = field(default=())
    requires_human: bool = False
    human_reason: str | None = None


#: Ordem é semântica: a primeira regra com termo presente vence.
ROUTING_RULES: tuple[RoutingRule, ...] = (
    RoutingRule(
        rule_id="identity.blocked",
        executor=ExecutorKind.HUMAN_GATE,
        terms=(
            "consentimento",
            "admin consent",
            "permissao",
            "permission",
            "credencial",
            "credential",
            "segredo",
            "secret",
            "token expirado",
            "expired token",
            "unauthorized",
            "forbidden",
            "403",
            "401",
        ),
        human_reason="identity_or_permission_missing",
    ),
    RoutingRule(
        rule_id="ci.repair",
        executor=ExecutorKind.CI_REPAIR,
        terms=(
            "ci",
            "workflow",
            "pipeline",
            "check",
            "gate",
            "github actions",
            "job falhou",
            "build quebrado",
            "smoke",
        ),
    ),
    RoutingRule(
        rule_id="microsoft.graph",
        executor=ExecutorKind.GRAPH,
        terms=(
            "graph",
            "teams",
            "planner",
            "sharepoint",
            "outlook",
            "m365",
            "microsoft 365",
            "power platform",
        ),
    ),
    RoutingRule(
        rule_id="data.sql",
        executor=ExecutorKind.SQL,
        terms=("sql", "sql server", "banco de dados", "database", "stored procedure", "t-sql"),
    ),
    RoutingRule(
        rule_id="artifact.drive",
        executor=ExecutorKind.DRIVE,
        terms=("drive", "google drive", "planilha", "excel", "xlsx", "artefato", "upload"),
    ),
    RoutingRule(
        rule_id="desktop.command_gateway",
        executor=ExecutorKind.COMMAND_GATEWAY,
        terms=("remote desktop", "command gateway", "terminal", "maquina local", "powershell"),
    ),
    RoutingRule(
        rule_id="scm.github",
        executor=ExecutorKind.GITHUB,
        terms=("pull request", "pr", "issue", "branch", "merge", "repositorio", "repository", "commit", "gitlab"),
    ),
    RoutingRule(
        rule_id="docs",
        executor=ExecutorKind.DOCS,
        terms=("documentacao", "documentation", "readme", "changelog", "runbook"),
    ),
)

UNCLASSIFIED_RULE = "unclassified"


def _normalizar(texto: str) -> str:
    """Normaliza para comparação por palavra inteira.

    Remove acentos, baixa a caixa, troca qualquer separador não alfanumérico por
    espaço e envolve o resultado em espaços. Assim ``" ci "`` casa com "CI/CD"
    mas não com "precificacao".
    """
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(ch for ch in sem_acento if not unicodedata.combining(ch))
    tokens = "".join(ch if ch.isalnum() else " " for ch in sem_acento.lower()).split()
    return f" {' '.join(tokens)} "


class ExecutorRouter:
    """Classificador determinístico de solicitações em executores."""

    def __init__(self, rules: tuple[RoutingRule, ...] = ROUTING_RULES) -> None:
        self._rules = rules

    def route(self, entrada: WorkRequestInput) -> RoutingDecision:
        corpus = _normalizar(
            " ".join(
                parte
                for parte in (entrada.title, entrada.target_system or "", *entrada.signals)
                if parte
            )
        )
        for rule in self._rules:
            encontrados = tuple(termo for termo in rule.terms if _termo_presente(corpus, termo))
            if encontrados:
                return RoutingDecision(
                    executor=rule.executor,
                    rule_id=rule.rule_id,
                    matched_terms=encontrados,
                    requires_human=rule.executor is ExecutorKind.HUMAN_GATE,
                    human_reason=rule.human_reason,
                )
        return RoutingDecision(
            executor=ExecutorKind.HUMAN_GATE,
            rule_id=UNCLASSIFIED_RULE,
            requires_human=True,
            human_reason="no_matching_executor_rule",
        )


def _termo_presente(corpus_normalizado: str, termo: str) -> bool:
    alvo = _normalizar(termo)
    return bool(alvo.strip()) and alvo in corpus_normalizado
