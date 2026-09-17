"""Evidence Ledger: registro canônico de "comprovadamente concluído".

Regras estruturais:

* evidência é sempre vinculada a ``(request_id, sha)``. Evidência de outro SHA
  não comprova o SHA atual;
* registrar evidência em um SHA novo **invalida** (supersede) o registro
  anterior, em vez de acumular provas de versões diferentes;
* uma falha em qualquer verificação leva a ``BLOCKED``: parcialidade não é
  arredondada para sucesso;
* ``EVIDENCED`` exige as quatro verificações obrigatórias em PASS — caso
  positivo, controle negativo, idempotência e leitura por fonte independente.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator

from app.domain.central.models import Environment, agora


class EvidenceCheck(str, Enum):
    POSITIVE = "positive"
    NEGATIVE_CONTROL = "negative_control"
    IDEMPOTENCY = "idempotency"
    INDEPENDENT_READ = "independent_read"


REQUIRED_CHECKS: frozenset[EvidenceCheck] = frozenset(EvidenceCheck)


class CheckResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    PENDING = "PENDING"


class EvidenceStatus(str, Enum):
    NOT_VALIDATED = "NOT_VALIDATED"
    PARTIAL = "PARTIAL"
    EVIDENCED = "EVIDENCED"
    BLOCKED = "BLOCKED"
    SUPERSEDED = "SUPERSEDED"


class EvidenceRecordInput(BaseModel):
    model_config = {"extra": "forbid"}

    request_id: str = Field(min_length=1, max_length=200)
    sha: str = Field(pattern=r"^[a-f0-9]{7,40}$")
    environment: Environment
    checks: dict[EvidenceCheck, CheckResult]
    production_touched: bool = False
    evidence_run_url: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validar_checks(self) -> "EvidenceRecordInput":
        if not self.checks:
            raise ValueError("ao menos uma verificação deve ser informada")
        return self


class EvidenceRecord(BaseModel):
    request_id: str
    sha: str
    environment: Environment
    checks: dict[EvidenceCheck, CheckResult]
    production_touched: bool
    evidence_run_url: str | None
    status: EvidenceStatus
    recorded_at: datetime
    superseded_by_sha: str | None = None

    @property
    def missing_checks(self) -> tuple[EvidenceCheck, ...]:
        return tuple(
            check
            for check in sorted(REQUIRED_CHECKS, key=lambda item: item.value)
            if self.checks.get(check, CheckResult.PENDING) is not CheckResult.PASS
        )


def derivar_status(checks: dict[EvidenceCheck, CheckResult]) -> EvidenceStatus:
    if any(result is CheckResult.FAIL for result in checks.values()):
        return EvidenceStatus.BLOCKED
    aprovadas = {check for check, result in checks.items() if result is CheckResult.PASS}
    if REQUIRED_CHECKS.issubset(aprovadas):
        return EvidenceStatus.EVIDENCED
    if aprovadas:
        return EvidenceStatus.PARTIAL
    return EvidenceStatus.NOT_VALIDATED


@dataclass(frozen=True)
class EvidenceApplication:
    """Resultado de aplicar uma entrada de evidência sobre o registro corrente."""

    registro: EvidenceRecord
    #: Preenchido quando o SHA mudou: o registro anterior passa a SUPERSEDED.
    anterior_invalidado: EvidenceRecord | None = None


def aplicar_evidencia(
    anterior: EvidenceRecord | None, entrada: EvidenceRecordInput
) -> EvidenceApplication:
    """Regra canônica de evidência, independente de onde o estado é guardado.

    Memória e Redis compartilham esta função para que a semântica de mesclagem,
    invalidação por SHA e derivação de status não divirja entre backends.
    """
    checks = dict(entrada.checks)
    invalidado: EvidenceRecord | None = None

    if anterior is not None and anterior.sha == entrada.sha:
        # Mesmo SHA: as verificações se acumulam; a mais recente prevalece.
        mescladas = dict(anterior.checks)
        mescladas.update(checks)
        checks = mescladas
    elif anterior is not None:
        invalidado = anterior.model_copy(
            update={"status": EvidenceStatus.SUPERSEDED, "superseded_by_sha": entrada.sha}
        )

    registro = EvidenceRecord(
        request_id=entrada.request_id,
        sha=entrada.sha,
        environment=entrada.environment,
        checks=checks,
        production_touched=entrada.production_touched,
        evidence_run_url=entrada.evidence_run_url,
        status=derivar_status(checks),
        recorded_at=agora(),
    )
    return EvidenceApplication(registro=registro, anterior_invalidado=invalidado)


def status_valido_para_sha(registro: EvidenceRecord | None, sha: str | None) -> EvidenceStatus:
    """Status que vale para o SHA informado; evidência de outro SHA não conta."""
    if registro is None:
        return EvidenceStatus.NOT_VALIDATED
    if sha is not None and registro.sha != sha:
        return EvidenceStatus.NOT_VALIDATED
    return registro.status


class EvidenceLedger:
    """Ledger em memória, uma entrada corrente por solicitação e histórico imutável."""

    def __init__(self) -> None:
        self._corrente: dict[str, EvidenceRecord] = {}
        self._historico: list[EvidenceRecord] = []

    def registrar(self, entrada: EvidenceRecordInput) -> EvidenceRecord:
        anterior = self._corrente.get(entrada.request_id)
        aplicacao = aplicar_evidencia(anterior, entrada)

        if aplicacao.anterior_invalidado is not None and anterior is not None:
            self._substituir_no_historico(anterior, aplicacao.anterior_invalidado)

        registro = aplicacao.registro
        self._corrente[entrada.request_id] = registro
        self._historico.append(registro)
        return registro

    def obter(self, request_id: str) -> EvidenceRecord | None:
        return self._corrente.get(request_id)

    def status_para(self, request_id: str, sha: str | None) -> EvidenceStatus:
        """Status válido para o SHA informado.

        Evidência de outro SHA nunca é reaproveitada: devolve NOT_VALIDATED.
        """
        return status_valido_para_sha(self._corrente.get(request_id), sha)

    def historico(self, request_id: str) -> tuple[EvidenceRecord, ...]:
        return tuple(item for item in self._historico if item.request_id == request_id)

    def _substituir_no_historico(self, antigo: EvidenceRecord, novo: EvidenceRecord) -> None:
        for indice, item in enumerate(self._historico):
            if item is antigo:
                self._historico[indice] = novo
                return
