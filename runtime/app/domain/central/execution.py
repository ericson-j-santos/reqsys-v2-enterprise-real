"""Contrato de execução da Central.

Um executor recebe uma Solicitação de Trabalho admitida, produz o efeito real e
devolve **as verificações que de fato realizou** — nunca as que gostaria de ter
realizado. Verificação não executada volta como ``PENDING``, o que mantém a
solicitação em ``AWAITING_EVIDENCE`` em vez de concluí-la indevidamente.

É essa regra que impede o executor de transformar "rodou sem erro" em
"comprovadamente concluído".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.domain.central.evidence_ledger import CheckResult, EvidenceCheck


class ExecutionOutcome(str, Enum):
    #: O efeito foi produzido; as verificações acompanham o resultado.
    SUCCESS = "SUCCESS"
    #: O executor tentou e falhou. Vira bloqueio com causa e próxima ação.
    FAILED = "FAILED"
    #: O executor não pode sequer tentar (falta configuração, identidade, SHA).
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class ExecutionResult:
    outcome: ExecutionOutcome
    #: Apenas verificações realmente executadas. As ausentes contam como PENDING.
    checks: dict[EvidenceCheck, CheckResult] = field(default_factory=dict)
    evidence_run_url: str | None = None
    #: Causa, já sanitizada, quando FAILED ou BLOCKED.
    blocker: str | None = None
    #: O que precisa acontecer para destravar. Obrigatório em FAILED/BLOCKED.
    next_action: str | None = None
    detail: str | None = None

    def __post_init__(self) -> None:
        if self.outcome is not ExecutionOutcome.SUCCESS and not (self.blocker and self.next_action):
            raise ValueError("resultado não bem-sucedido exige blocker e next_action")
        if self.outcome is ExecutionOutcome.SUCCESS and not self.checks:
            raise ValueError("execução bem-sucedida deve informar ao menos uma verificação")

    @property
    def verificacoes_pendentes(self) -> tuple[EvidenceCheck, ...]:
        return tuple(
            check
            for check in sorted(EvidenceCheck, key=lambda item: item.value)
            if self.checks.get(check, CheckResult.PENDING) is not CheckResult.PASS
        )


class ExecutorAdapter:
    """Interface de um executor concreto.

    Implementações não levantam exceção para falha de negócio: devolvem
    ``ExecutionResult`` com ``FAILED``/``BLOCKED`` e a causa, para que o worker
    registre um bloqueio acionável em vez de um stack trace.
    """

    async def executar(self, solicitacao) -> ExecutionResult:
        """Produz o efeito e devolve as verificações realizadas."""
        raise NotImplementedError
