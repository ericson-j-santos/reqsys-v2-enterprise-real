"""Persistência do plano de controle da Central.

Duas implementações com a mesma semântica:

* ``InMemoryCentralStore`` — estado no processo, para DEV e testes;
* ``RedisCentralStore`` — estado durável, sobrevive a reinício e é compartilhado
  entre réplicas da API e workers.

Concorrência: a criação é atômica por ``SET NX`` e toda atualização passa por um
compare-and-swap otimista (``WATCH``/``MULTI``), de modo que duas réplicas não
percam escritas uma da outra. Um ``asyncio.Lock`` de processo não daria essa
garantia e por isso não é usado como mecanismo primário.
"""

from __future__ import annotations

import asyncio
from typing import Callable, Protocol

from redis.asyncio import Redis
from redis.exceptions import WatchError

from app.domain.central.evidence_ledger import (
    EvidenceRecord,
    EvidenceRecordInput,
    EvidenceStatus,
    aplicar_evidencia,
    status_valido_para_sha,
)
from app.domain.central.models import WorkRequest

#: Uma mutação recebe a solicitação corrente e devolve a nova. Pode levantar
#: exceção para recusar a transição; nada é gravado nesse caso.
Mutator = Callable[[WorkRequest], WorkRequest]

CAS_MAX_RETRIES = 5


class ConcurrentUpdateError(RuntimeError):
    """O compare-and-swap não convergiu: outra réplica está escrevendo."""


class CentralStore(Protocol):
    async def criar_se_ausente(self, solicitacao: WorkRequest) -> tuple[WorkRequest, bool]: ...

    async def obter(self, request_id: str) -> WorkRequest | None: ...

    async def listar(self) -> list[WorkRequest]: ...

    async def atualizar(self, request_id: str, mutator: Mutator) -> WorkRequest | None: ...

    async def registrar_evidencia(self, entrada: EvidenceRecordInput) -> EvidenceRecord: ...

    async def obter_evidencia(self, request_id: str) -> EvidenceRecord | None: ...

    async def historico_evidencia(self, request_id: str) -> tuple[EvidenceRecord, ...]: ...

    async def status_evidencia(self, request_id: str, sha: str | None) -> EvidenceStatus: ...


class InMemoryCentralStore:
    """Estado no processo. Perde tudo no reinício — use apenas em DEV e testes."""

    def __init__(self) -> None:
        self._requests: dict[str, WorkRequest] = {}
        self._evidencia: dict[str, EvidenceRecord] = {}
        self._historico: list[EvidenceRecord] = []
        self._lock = asyncio.Lock()

    async def criar_se_ausente(self, solicitacao: WorkRequest) -> tuple[WorkRequest, bool]:
        async with self._lock:
            existente = self._requests.get(solicitacao.request_id)
            if existente is not None:
                return existente.model_copy(deep=True), False
            self._requests[solicitacao.request_id] = solicitacao
            return solicitacao.model_copy(deep=True), True

    async def obter(self, request_id: str) -> WorkRequest | None:
        solicitacao = self._requests.get(request_id)
        return solicitacao.model_copy(deep=True) if solicitacao else None

    async def listar(self) -> list[WorkRequest]:
        return [item.model_copy(deep=True) for item in self._requests.values()]

    async def atualizar(self, request_id: str, mutator: Mutator) -> WorkRequest | None:
        async with self._lock:
            atual = self._requests.get(request_id)
            if atual is None:
                return None
            atualizada = mutator(atual.model_copy(deep=True))
            self._requests[request_id] = atualizada
            return atualizada.model_copy(deep=True)

    async def registrar_evidencia(self, entrada: EvidenceRecordInput) -> EvidenceRecord:
        async with self._lock:
            anterior = self._evidencia.get(entrada.request_id)
            aplicacao = aplicar_evidencia(anterior, entrada)
            if aplicacao.anterior_invalidado is not None and anterior is not None:
                for indice, item in enumerate(self._historico):
                    if item is anterior:
                        self._historico[indice] = aplicacao.anterior_invalidado
                        break
            self._evidencia[entrada.request_id] = aplicacao.registro
            self._historico.append(aplicacao.registro)
            return aplicacao.registro

    async def obter_evidencia(self, request_id: str) -> EvidenceRecord | None:
        return self._evidencia.get(request_id)

    async def historico_evidencia(self, request_id: str) -> tuple[EvidenceRecord, ...]:
        return tuple(item for item in self._historico if item.request_id == request_id)

    async def status_evidencia(self, request_id: str, sha: str | None) -> EvidenceStatus:
        return status_valido_para_sha(self._evidencia.get(request_id), sha)


class RedisCentralStore:
    """Estado durável em Redis, compartilhado entre réplicas.

    Chaves (sob ``prefix``):

    * ``:request:<id>``            JSON da solicitação
    * ``:requests``                SET com os ids, para listagem
    * ``:evidence:<id>``           JSON do registro corrente de evidência
    * ``:evidence:<id>:history``   LIST append-only com o histórico
    """

    def __init__(self, redis: Redis, prefix: str = "reqsys:runtime:central") -> None:
        self.redis = redis
        self.prefix = prefix

    def _request_key(self, request_id: str) -> str:
        return f"{self.prefix}:request:{request_id}"

    def _index_key(self) -> str:
        return f"{self.prefix}:requests"

    def _evidence_key(self, request_id: str) -> str:
        return f"{self.prefix}:evidence:{request_id}"

    def _history_key(self, request_id: str) -> str:
        return f"{self.prefix}:evidence:{request_id}:history"

    async def criar_se_ausente(self, solicitacao: WorkRequest) -> tuple[WorkRequest, bool]:
        key = self._request_key(solicitacao.request_id)
        criado = await self.redis.set(key, solicitacao.model_dump_json(), nx=True)
        if not criado:
            existente = await self.obter(solicitacao.request_id)
            if existente is not None:
                return existente, False
            # Corrida rara: a chave expirou ou foi removida entre SET NX e GET.
            await self.redis.set(key, solicitacao.model_dump_json())
        await self.redis.sadd(self._index_key(), solicitacao.request_id)
        return solicitacao, True

    async def obter(self, request_id: str) -> WorkRequest | None:
        raw = await self.redis.get(self._request_key(request_id))
        return WorkRequest.model_validate_json(raw) if raw else None

    async def listar(self) -> list[WorkRequest]:
        ids = await self.redis.smembers(self._index_key())
        if not ids:
            return []
        ordenados = sorted(ids)
        valores = await self.redis.mget([self._request_key(item) for item in ordenados])
        solicitacoes: list[WorkRequest] = []
        orfaos: list[str] = []
        for request_id, raw in zip(ordenados, valores):
            if raw:
                solicitacoes.append(WorkRequest.model_validate_json(raw))
            else:
                orfaos.append(request_id)
        if orfaos:
            # Índice não pode divergir do estado: um id sem chave é removido.
            await self.redis.srem(self._index_key(), *orfaos)
        return solicitacoes

    async def atualizar(self, request_id: str, mutator: Mutator) -> WorkRequest | None:
        key = self._request_key(request_id)
        for _ in range(CAS_MAX_RETRIES):
            async with self.redis.pipeline(transaction=True) as pipe:
                try:
                    await pipe.watch(key)
                    raw = await pipe.get(key)
                    if not raw:
                        await pipe.unwatch()
                        return None
                    atual = WorkRequest.model_validate_json(raw)
                    # O mutator pode recusar a transição; nada é gravado então.
                    atualizada = mutator(atual)
                    pipe.multi()
                    pipe.set(key, atualizada.model_dump_json())
                    await pipe.execute()
                    return atualizada
                except WatchError:
                    continue
        raise ConcurrentUpdateError(f"não foi possível atualizar {request_id} sem conflito")

    async def registrar_evidencia(self, entrada: EvidenceRecordInput) -> EvidenceRecord:
        key = self._evidence_key(entrada.request_id)
        history_key = self._history_key(entrada.request_id)
        for _ in range(CAS_MAX_RETRIES):
            async with self.redis.pipeline(transaction=True) as pipe:
                try:
                    await pipe.watch(key)
                    raw = await pipe.get(key)
                    anterior = EvidenceRecord.model_validate_json(raw) if raw else None
                    aplicacao = aplicar_evidencia(anterior, entrada)
                    pipe.multi()
                    if aplicacao.anterior_invalidado is not None:
                        # O histórico é append-only: a invalidação por mudança de
                        # SHA é registrada como um novo evento, não sobrescreve.
                        pipe.rpush(history_key, aplicacao.anterior_invalidado.model_dump_json())
                    pipe.set(key, aplicacao.registro.model_dump_json())
                    pipe.rpush(history_key, aplicacao.registro.model_dump_json())
                    await pipe.execute()
                    return aplicacao.registro
                except WatchError:
                    continue
        raise ConcurrentUpdateError(f"não foi possível registrar evidência de {entrada.request_id}")

    async def obter_evidencia(self, request_id: str) -> EvidenceRecord | None:
        raw = await self.redis.get(self._evidence_key(request_id))
        return EvidenceRecord.model_validate_json(raw) if raw else None

    async def historico_evidencia(self, request_id: str) -> tuple[EvidenceRecord, ...]:
        registros = await self.redis.lrange(self._history_key(request_id), 0, -1)
        return tuple(EvidenceRecord.model_validate_json(item) for item in registros)

    async def status_evidencia(self, request_id: str, sha: str | None) -> EvidenceStatus:
        return status_valido_para_sha(await self.obter_evidencia(request_id), sha)
