"""Testes do store da Central: paridade de semântica entre memória e Redis.

O mesmo corpo de teste roda contra ``InMemoryCentralStore`` e contra
``RedisCentralStore`` (sobre um Redis falso com WATCH/MULTI), de modo que uma
divergência de comportamento entre os backends reprove aqui e não em produção.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from redis.exceptions import WatchError

from app.domain.central.evidence_ledger import (
    CheckResult,
    EvidenceCheck,
    EvidenceRecordInput,
    EvidenceStatus,
)
from app.domain.central.models import (
    Environment,
    ExecutorKind,
    Priority,
    WorkRequest,
    WorkRequestStatus,
)
from app.infrastructure.repositories.central_store import (
    ConcurrentUpdateError,
    InMemoryCentralStore,
    RedisCentralStore,
)

SHA_A = "a" * 40
SHA_B = "b" * 40


class FakeRedisPipeline:
    """Pipeline com semântica de WATCH/MULTI suficiente para o CAS do store."""

    def __init__(self, redis: "FakeRedis") -> None:
        self._redis = redis
        self._watched: dict[str, str | None] = {}
        self._commands: list[tuple[str, tuple]] = []
        self._buffering = False

    async def __aenter__(self) -> "FakeRedisPipeline":
        return self

    async def __aexit__(self, *_exc) -> None:
        self._watched.clear()
        self._commands.clear()
        self._buffering = False

    async def watch(self, key: str) -> None:
        self._watched[key] = self._redis.values.get(key)

    async def unwatch(self) -> None:
        self._watched.clear()

    async def get(self, key: str) -> str | None:
        return self._redis.values.get(key)

    def multi(self) -> None:
        self._buffering = True

    def set(self, key: str, value: str) -> None:
        self._commands.append(("set", (key, value)))

    def rpush(self, key: str, value: str) -> None:
        self._commands.append(("rpush", (key, value)))

    async def execute(self) -> list:
        for key, esperado in self._watched.items():
            if self._redis.values.get(key) != esperado:
                raise WatchError("watched key changed")
        resultados = []
        for nome, args in self._commands:
            resultados.append(await getattr(self._redis, nome)(*args))
        self._commands.clear()
        self._watched.clear()
        return resultados


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.sets: dict[str, set[str]] = {}
        self.lists: dict[str, list[str]] = {}
        #: Chaves que devem sofrer uma escrita concorrente antes do próximo EXEC.
        self.interferir_em: dict[str, int] = {}

    async def set(self, key: str, value: str, nx: bool = False) -> bool:
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def mget(self, keys: list[str]) -> list[str | None]:
        return [self.values.get(key) for key in keys]

    async def sadd(self, key: str, *values: str) -> int:
        alvo = self.sets.setdefault(key, set())
        antes = len(alvo)
        alvo.update(values)
        return len(alvo) - antes

    async def srem(self, key: str, *values: str) -> int:
        alvo = self.sets.setdefault(key, set())
        removidos = len(alvo & set(values))
        alvo.difference_update(values)
        return removidos

    async def smembers(self, key: str) -> set[str]:
        return set(self.sets.get(key, set()))

    async def rpush(self, key: str, value: str) -> int:
        self.lists.setdefault(key, []).append(value)
        return len(self.lists[key])

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        itens = self.lists.get(key, [])
        return itens[start:] if end == -1 else itens[start : end + 1]

    def pipeline(self, transaction: bool = True) -> FakeRedisPipeline:
        pipeline = FakeRedisPipeline(self)
        restantes = self.interferir_em

        original_execute = pipeline.execute

        async def execute_com_interferencia():
            for key in list(restantes):
                if restantes[key] > 0:
                    restantes[key] -= 1
                    # Escrita concorrente de outra réplica entre WATCH e EXEC.
                    self.values[key] = self.values.get(key, "") + " "
            return await original_execute()

        pipeline.execute = execute_com_interferencia  # type: ignore[method-assign]
        return pipeline


def solicitacao(request_id: str = "WR-1", status=WorkRequestStatus.RECEIVED, **kw) -> WorkRequest:
    momento = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)
    base = {
        "request_id": request_id,
        "title": "Reparar workflow de CI",
        "project": "reqsys",
        "environment": Environment.DEV,
        "priority": Priority.P1,
        "root_cause_id": "rc-ci",
        "correlation_id": "corr-12345678",
        "executor": ExecutorKind.CI_REPAIR,
        "routing_rule": "ci.repair",
        "status": status,
        "created_at": momento,
        "updated_at": momento,
    }
    base.update(kw)
    return WorkRequest(**base)


def evidencia(request_id="WR-1", sha=SHA_A, **checks) -> EvidenceRecordInput:
    return EvidenceRecordInput(
        request_id=request_id,
        sha=sha,
        environment=Environment.DEV,
        checks={EvidenceCheck(k): CheckResult(v) for k, v in checks.items()},
    )


TODOS_PASS = {
    "positive": "PASS",
    "negative_control": "PASS",
    "idempotency": "PASS",
    "independent_read": "PASS",
}


@pytest.fixture(params=["memoria", "redis"])
def store(request):
    if request.param == "memoria":
        return InMemoryCentralStore()
    return RedisCentralStore(FakeRedis(), prefix="test:central")


# --------------------------------------------------------------------------- #
# Paridade entre backends
# --------------------------------------------------------------------------- #


async def test_criacao_e_idempotente(store):
    primeira, criada = await store.criar_se_ausente(solicitacao())
    assert criada is True
    segunda, recriada = await store.criar_se_ausente(solicitacao(title="outro titulo"))
    assert recriada is False
    # O conteúdo original prevalece: um replay não sobrescreve o registro.
    assert segunda.title == primeira.title
    assert len(await store.listar()) == 1


async def test_obter_inexistente_devolve_none(store):
    assert await store.obter("WR-INEXISTENTE") is None


async def test_atualizar_persiste_e_devolve_novo_estado(store):
    await store.criar_se_ausente(solicitacao())
    atualizada = await store.atualizar(
        "WR-1", lambda item: item.model_copy(update={"status": WorkRequestStatus.ADMITTED})
    )
    assert atualizada is not None and atualizada.status is WorkRequestStatus.ADMITTED
    relido = await store.obter("WR-1")
    assert relido is not None and relido.status is WorkRequestStatus.ADMITTED


async def test_atualizar_inexistente_devolve_none(store):
    assert await store.atualizar("WR-AUSENTE", lambda item: item) is None


async def test_mutator_que_recusa_nao_grava(store):
    await store.criar_se_ausente(solicitacao())

    def recusa(_item):
        raise ValueError("transição recusada")

    with pytest.raises(ValueError, match="recusada"):
        await store.atualizar("WR-1", recusa)

    relido = await store.obter("WR-1")
    assert relido is not None and relido.status is WorkRequestStatus.RECEIVED


async def test_evidencia_acumula_no_mesmo_sha(store):
    await store.criar_se_ausente(solicitacao())
    parcial = await store.registrar_evidencia(evidencia(positive="PASS", idempotency="PASS"))
    assert parcial.status is EvidenceStatus.PARTIAL

    completo = await store.registrar_evidencia(
        evidencia(negative_control="PASS", independent_read="PASS")
    )
    assert completo.status is EvidenceStatus.EVIDENCED
    assert await store.status_evidencia("WR-1", SHA_A) is EvidenceStatus.EVIDENCED


async def test_evidencia_de_sha_novo_invalida_anterior(store):
    await store.criar_se_ausente(solicitacao())
    await store.registrar_evidencia(evidencia(**TODOS_PASS))
    await store.registrar_evidencia(evidencia(sha=SHA_B, positive="PASS"))

    assert await store.status_evidencia("WR-1", SHA_B) is EvidenceStatus.PARTIAL
    # Evidência do SHA antigo não vale mais para nenhuma conclusão.
    assert await store.status_evidencia("WR-1", SHA_A) is EvidenceStatus.NOT_VALIDATED

    historico = await store.historico_evidencia("WR-1")
    superseded = [item for item in historico if item.status is EvidenceStatus.SUPERSEDED]
    assert len(superseded) == 1
    assert superseded[0].sha == SHA_A
    assert superseded[0].superseded_by_sha == SHA_B


async def test_status_evidencia_sem_registro(store):
    assert await store.status_evidencia("WR-1", SHA_A) is EvidenceStatus.NOT_VALIDATED


async def test_listar_vazio(store):
    assert await store.listar() == []


# --------------------------------------------------------------------------- #
# Específicos do backend Redis
# --------------------------------------------------------------------------- #


async def test_redis_cas_reexecuta_apos_escrita_concorrente():
    redis = FakeRedis()
    store = RedisCentralStore(redis, prefix="test:central")
    await store.criar_se_ausente(solicitacao())
    # Uma réplica concorrente escreve entre WATCH e EXEC na primeira tentativa.
    redis.interferir_em[store._request_key("WR-1")] = 1

    atualizada = await store.atualizar(
        "WR-1", lambda item: item.model_copy(update={"status": WorkRequestStatus.ADMITTED})
    )
    assert atualizada is not None and atualizada.status is WorkRequestStatus.ADMITTED


async def test_redis_cas_desiste_sob_conflito_permanente():
    redis = FakeRedis()
    store = RedisCentralStore(redis, prefix="test:central")
    await store.criar_se_ausente(solicitacao())
    redis.interferir_em[store._request_key("WR-1")] = 99

    with pytest.raises(ConcurrentUpdateError):
        await store.atualizar("WR-1", lambda item: item)


async def test_redis_listar_descarta_id_orfao_do_indice():
    redis = FakeRedis()
    store = RedisCentralStore(redis, prefix="test:central")
    await store.criar_se_ausente(solicitacao("WR-1"))
    await store.criar_se_ausente(solicitacao("WR-2"))
    # A chave sumiu (expiração ou limpeza), mas o índice ainda a referencia.
    del redis.values[store._request_key("WR-2")]

    listadas = await store.listar()
    assert [item.request_id for item in listadas] == ["WR-1"]
    assert await redis.smembers(store._index_key()) == {"WR-1"}
