from fastapi.testclient import TestClient

from app.application.services.job_service import JobService
from app.core.config import RuntimeSettings
from app.domain.models.job_assincrono import AsyncJobCreateRequest, JobStatus, TipoOperacao
from app.infrastructure.http.httpx_gateway import HttpxGateway
from app.infrastructure.queue.asyncio_queue import AsyncioQueueGateway
from app.infrastructure.repositories.job_repository_memoria import JobRepositoryMemoria
from app.main import app


class DummyHttpGateway(HttpxGateway):
    async def post_json(self, url: str, payload: dict, correlation_id: str) -> dict:
        return {"ok": True, "url": url, "correlation_id": correlation_id, "payload": payload}


def test_post_jobs_retorna_202_e_location() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/jobs",
        json={
            "origem": "power_automate",
            "tipo_operacao": "enviar_resposta",
            "destino": "reqsys_runtime",
            "payload": {"requisito_id": "REQ-001", "status": "aprovado"},
            "metadata": {"versao_contrato": "0.5.0", "correlation_id": "teste-001"},
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["correlation_id"] == "teste-001"
    assert response.headers["location"] == body["status_url"]


def test_get_job_retorna_404_para_job_inexistente() -> None:
    client = TestClient(app)

    response = client.get("/api/jobs/JOB-INEXISTENTE")

    assert response.status_code == 404


async def test_service_processa_job_simulado_com_sucesso() -> None:
    repository = JobRepositoryMemoria()
    queue = AsyncioQueueGateway()
    service = JobService(repository, queue, DummyHttpGateway(), RuntimeSettings(max_tentativas=3))

    accepted = await service.criar_job(
        AsyncJobCreateRequest(
            origem="power_automate",
            tipo_operacao=TipoOperacao.ENVIAR_RESPOSTA,
            destino="reqsys_runtime",
            payload={"requisito_id": "REQ-001"},
        )
    )

    await service.processar_job(accepted.job_id)
    status = await service.consultar_job(accepted.job_id)

    assert status.status == JobStatus.COMPLETED
    assert status.tentativas == 1
    assert status.resultado is not None
    assert status.resultado["modo"] == "simulado_dev"


async def test_service_processa_job_com_destino_url_usando_gateway() -> None:
    repository = JobRepositoryMemoria()
    queue = AsyncioQueueGateway()
    service = JobService(repository, queue, DummyHttpGateway(), RuntimeSettings(max_tentativas=3))

    accepted = await service.criar_job(
        AsyncJobCreateRequest(
            origem="power_automate",
            tipo_operacao=TipoOperacao.NOTIFICAR_STATUS,
            destino="api_externa",
            destino_url="https://api.exemplo.com/callback",
            payload={"status": "ok"},
            metadata={"correlation_id": "corr-123"},
        )
    )

    await service.processar_job(accepted.job_id)
    status = await service.consultar_job(accepted.job_id)

    assert status.status == JobStatus.COMPLETED
    assert status.resultado is not None
    assert status.resultado["correlation_id"] == "corr-123"
