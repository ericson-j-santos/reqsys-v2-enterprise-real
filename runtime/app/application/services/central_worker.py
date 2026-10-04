"""Worker da Central: puxa o próximo item, executa, registra evidência.

É o elo que faltava para a Central deixar de ser um painel e passar a mover
trabalho:

    next -> EXECUTING -> executor -> evidência -> EVIDENCED

Invariantes que o worker preserva:

* **nunca conclui sem evidência completa.** Ele registra o que o executor
  comprovou e tenta a conclusão; se faltar verificação, a solicitação fica em
  ``AWAITING_EVIDENCE`` e o ciclo reporta isso, em vez de forçar ``EVIDENCED``;
* **nenhuma falha vira silêncio.** Executor ausente, sem SHA, indisponível ou
  com verificação reprovada viram ``BLOCKED`` com causa e próxima ação;
* **concorrência é do store.** Se outra réplica pegou o mesmo item primeiro, a
  transição é recusada e este ciclo simplesmente cede a vez.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum

from app.application.services.central_service import (
    CentralService,
    InvalidTransitionError,
    WorkRequestNotFoundError,
)
from app.domain.central.evidence_ledger import (
    CheckResult,
    EvidenceCheck,
    EvidenceRecordInput,
    EvidenceStatus,
)
from app.domain.central.execution import ExecutionOutcome, ExecutionResult
from app.domain.central.models import ExecutorKind, WorkRequest, WorkRequestStatus
from app.infrastructure.executors.registry import ExecutorRegistry

logger = logging.getLogger("reqsys.runtime.central.worker")


class CicloResultado(str, Enum):
    OCIOSO = "OCIOSO"
    EVIDENCIADO = "EVIDENCIADO"
    AGUARDANDO_EVIDENCIA = "AGUARDANDO_EVIDENCIA"
    BLOQUEADO = "BLOQUEADO"
    CEDIDO = "CEDIDO"


@dataclass(frozen=True)
class CicloRelatorio:
    resultado: CicloResultado
    request_id: str | None = None
    executor: ExecutorKind | None = None
    evidence_status: EvidenceStatus | None = None
    verificacoes_pendentes: tuple[EvidenceCheck, ...] = ()
    blocker: str | None = None


class CentralWorker:
    def __init__(
        self,
        central: CentralService,
        registry: ExecutorRegistry,
        intervalo_ocioso_segundos: float = 5.0,
    ) -> None:
        self._central = central
        self._registry = registry
        self._intervalo = intervalo_ocioso_segundos

    async def executar_um_ciclo(self, executor: ExecutorKind | None = None) -> CicloRelatorio:
        solicitacao = await self._central.proximo_item(executor)
        if solicitacao is None:
            return CicloRelatorio(resultado=CicloResultado.OCIOSO)

        adaptador = self._registry.para(solicitacao.executor)
        if adaptador is None:
            return await self._bloquear(
                solicitacao,
                blocker=f"executor_nao_configurado:{solicitacao.executor.value}",
                next_action=(
                    "Configurar CENTRAL_EXECUTOR_ENDPOINTS para "
                    f"'{solicitacao.executor.value}' ou rotear a solicitação para outro executor."
                ),
            )

        try:
            solicitacao = await self._central.transicionar(
                solicitacao.request_id, WorkRequestStatus.EXECUTING
            )
        except InvalidTransitionError:
            # Outra réplica assumiu este item entre o next e a transição.
            logger.info("ciclo_cedido", extra={"request_id": solicitacao.request_id})
            return CicloRelatorio(
                resultado=CicloResultado.CEDIDO,
                request_id=solicitacao.request_id,
                executor=solicitacao.executor,
            )
        except WorkRequestNotFoundError:
            return CicloRelatorio(resultado=CicloResultado.OCIOSO)

        try:
            resultado = await adaptador.executar(solicitacao)
        except Exception as exc:  # noqa: BLE001 - falha de executor vira bloqueio, não crash
            logger.exception("executor_falhou", extra={"request_id": solicitacao.request_id})
            resultado = ExecutionResult(
                outcome=ExecutionOutcome.FAILED,
                blocker=f"executor_excecao:{type(exc).__name__}",
                next_action="Investigar o executor: exceção não tratada durante a execução.",
            )

        if resultado.outcome is not ExecutionOutcome.SUCCESS:
            return await self._bloquear(
                solicitacao,
                blocker=resultado.blocker or "executor_falhou",
                next_action=resultado.next_action or "Investigar a falha do executor.",
                checks=resultado.checks,
            )

        return await self._concluir(solicitacao, resultado)

    async def _concluir(
        self, solicitacao: WorkRequest, resultado: ExecutionResult
    ) -> CicloRelatorio:
        registro = await self._central.registrar_evidencia(
            EvidenceRecordInput(
                request_id=solicitacao.request_id,
                sha=str(solicitacao.sha),
                environment=solicitacao.environment,
                checks=resultado.checks,
                production_touched=solicitacao.environment.value == "prod",
                evidence_run_url=resultado.evidence_run_url,
            )
        )

        if registro.status is not EvidenceStatus.EVIDENCED:
            # O executor comprovou parte. Concluir aqui seria exatamente o
            # falso positivo que a Central existe para impedir.
            pendentes = registro.missing_checks
            logger.info(
                "evidencia_incompleta",
                extra={"request_id": solicitacao.request_id, "pendentes": [c.value for c in pendentes]},
            )
            return CicloRelatorio(
                resultado=CicloResultado.AGUARDANDO_EVIDENCIA,
                request_id=solicitacao.request_id,
                executor=solicitacao.executor,
                evidence_status=registro.status,
                verificacoes_pendentes=pendentes,
            )

        try:
            final = await self._central.transicionar(
                solicitacao.request_id,
                WorkRequestStatus.EVIDENCED,
                next_action=None,
            )
        except InvalidTransitionError:
            # A solicitação saiu de AWAITING_EVIDENCE entre a evidência e a
            # conclusão (outra réplica, ou um bloqueio manual). A evidência
            # continua gravada; quem assumiu o item decide o desfecho.
            logger.info("conclusao_cedida", extra={"request_id": solicitacao.request_id})
            return CicloRelatorio(
                resultado=CicloResultado.CEDIDO,
                request_id=solicitacao.request_id,
                executor=solicitacao.executor,
                evidence_status=registro.status,
            )
        logger.info(
            "solicitacao_evidenciada",
            extra={"request_id": final.request_id, "sha": final.sha, "executor": final.executor.value},
        )
        return CicloRelatorio(
            resultado=CicloResultado.EVIDENCIADO,
            request_id=final.request_id,
            executor=final.executor,
            evidence_status=registro.status,
        )

    async def _bloquear(
        self,
        solicitacao: WorkRequest,
        blocker: str,
        next_action: str,
        checks: dict[EvidenceCheck, CheckResult] | None = None,
    ) -> CicloRelatorio:
        if checks and solicitacao.sha:
            # Verificação reprovada é evidência: fica registrada no ledger.
            await self._central.registrar_evidencia(
                EvidenceRecordInput(
                    request_id=solicitacao.request_id,
                    sha=solicitacao.sha,
                    environment=solicitacao.environment,
                    checks=checks,
                )
            )
        bloqueada = await self._central.transicionar(
            solicitacao.request_id,
            WorkRequestStatus.BLOCKED,
            blocker=blocker,
            next_action=next_action,
        )
        logger.warning(
            "solicitacao_bloqueada",
            extra={"request_id": bloqueada.request_id, "blocker": blocker},
        )
        return CicloRelatorio(
            resultado=CicloResultado.BLOQUEADO,
            request_id=bloqueada.request_id,
            executor=bloqueada.executor,
            blocker=blocker,
        )

    async def executar_continuamente(self) -> None:
        """Laço do worker. Ocioso dorme; erro inesperado não derruba o laço."""
        logger.info(
            "central_worker_iniciado",
            extra={"executores": [item.value for item in self._registry.configurados()]},
        )
        while True:
            try:
                relatorio = await self.executar_um_ciclo()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - o laço precisa sobreviver ao ciclo
                logger.exception("ciclo_central_falhou")
                await asyncio.sleep(self._intervalo)
                continue

            if relatorio.resultado is CicloResultado.OCIOSO:
                await asyncio.sleep(self._intervalo)
