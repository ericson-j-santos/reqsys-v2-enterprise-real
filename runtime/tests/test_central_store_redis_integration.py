"""Integração da Central contra um Redis real.

O teste falso de ``test_central_store.py`` prova a lógica; este prova que a
semântica assumida (SET NX, WATCH/MULTI, SMEMBERS/MGET, RPUSH) é a do servidor.
Habilitado apenas no workflow dedicado, como a integração de todo-events.
"""

from __future__ import annotations

import os
import uuid

import pytest
from redis.asyncio import Redis

from app.application.services.central_service import CentralService
from app.domain.central.evidence_ledger import (
    CheckResult,
    EvidenceCheck,
    EvidenceRecordInput,
    EvidenceStatus,
)
from app.domain.central.models import Environment, WorkRequestInput, WorkRequestStatus
from app.infrastructure.repositories.central_store import RedisCentralStore

pytestmark = pytest.mark.skipif(
    os.getenv("REQSYS_RUNTIME_REDIS_INTEGRATION") != "1",
    reason="integração Redis habilitada somente no workflow dedicado",
)

SHA_A = "a" * 40
SHA_B = "b" * 40


@pytest.fixture
async def store():
    redis = Redis.from_url(
        os.getenv("REQSYS_RUNTIME_REDIS_TEST_URL", "redis://localhost:6379/15"),
        decode_responses=True,
    )
    prefixo = f"test:central:{uuid.uuid4().hex[:8]}"
    try:
        yield RedisCentralStore(redis, prefix=prefixo)
    finally:
        chaves = [chave async for chave in redis.scan_iter(f"{prefixo}:*")]
        if chaves:
            await redis.delete(*chaves)
        await redis.aclose()


def entrada(**overrides) -> WorkRequestInput:
    base = {
        "title": "Reparar workflow de CI",
        "project": "reqsys",
        "root_cause_id": "rc-ci",
        "correlation_id": "corr-12345678",
        "signals": ["pipeline vermelho"],
    }
    base.update(overrides)
    return WorkRequestInput(**base)


async def test_ciclo_completo_e_durabilidade_em_redis_real(store):
    service = CentralService(store=store)
    criada = await service.registrar(entrada(sha=SHA_A))
    await service.aplicar_admissao()
    await service.transicionar(criada.request_id, WorkRequestStatus.EXECUTING)
    await service.registrar_evidencia(
        EvidenceRecordInput(
            request_id=criada.request_id,
            sha=SHA_A,
            environment=Environment.DEV,
            checks={check: CheckResult.PASS for check in EvidenceCheck},
        )
    )

    # Novo serviço sobre o mesmo Redis: o estado sobrevive ao processo.
    reiniciado = CentralService(store=store)
    relida = await reiniciado.obter(criada.request_id)
    assert relida.status is WorkRequestStatus.AWAITING_EVIDENCE
    assert (await reiniciado.obter_evidencia(criada.request_id)).status is EvidenceStatus.EVIDENCED

    final = await reiniciado.transicionar(criada.request_id, WorkRequestStatus.EVIDENCED)
    assert final.status is WorkRequestStatus.EVIDENCED


async def test_registro_concorrente_nao_duplica_em_redis_real(store):
    """Duas réplicas registrando o mesmo trabalho produzem uma única solicitação."""
    import asyncio

    servicos = [CentralService(store=store) for _ in range(5)]
    resultados = await asyncio.gather(*(s.registrar(entrada()) for s in servicos))

    assert len({item.request_id for item in resultados}) == 1
    assert len(await store.listar()) == 1


async def test_evidencia_de_sha_novo_invalida_anterior_em_redis_real(store):
    service = CentralService(store=store)
    criada = await service.registrar(entrada(sha=SHA_A))
    await service.registrar_evidencia(
        EvidenceRecordInput(
            request_id=criada.request_id,
            sha=SHA_A,
            environment=Environment.DEV,
            checks={check: CheckResult.PASS for check in EvidenceCheck},
        )
    )
    await service.registrar_evidencia(
        EvidenceRecordInput(
            request_id=criada.request_id,
            sha=SHA_B,
            environment=Environment.DEV,
            checks={EvidenceCheck.POSITIVE: CheckResult.PASS},
        )
    )

    assert await store.status_evidencia(criada.request_id, SHA_A) is EvidenceStatus.NOT_VALIDATED
    historico = await store.historico_evidencia(criada.request_id)
    superseded = [item for item in historico if item.status is EvidenceStatus.SUPERSEDED]
    assert len(superseded) == 1 and superseded[0].superseded_by_sha == SHA_B


async def test_transicao_concorrente_nao_perde_escrita_em_redis_real(store):
    """Só uma réplica consegue sair de ADMITTED para EXECUTING."""
    import asyncio

    from app.application.services.central_service import InvalidTransitionError

    service = CentralService(store=store)
    criada = await service.registrar(entrada())
    await service.aplicar_admissao()

    resultados = await asyncio.gather(
        *(
            CentralService(store=store).transicionar(criada.request_id, WorkRequestStatus.EXECUTING)
            for _ in range(4)
        ),
        return_exceptions=True,
    )
    sucessos = [item for item in resultados if not isinstance(item, Exception)]
    recusas = [item for item in resultados if isinstance(item, InvalidTransitionError)]

    assert len(sucessos) == 1
    assert len(recusas) == len(resultados) - 1
    relida = await store.obter(criada.request_id)
    assert relida is not None and relida.status is WorkRequestStatus.EXECUTING
