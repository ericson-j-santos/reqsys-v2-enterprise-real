from fastapi import APIRouter, Header

from app.core.correlation import definir_correlation_id, obter_correlation_id
from app.models.operational_intelligence_models import SinalRuntime
from app.services.autonomous_operation_service import AutonomousOperationService
from app.services.runtime_intelligence_service import RuntimeIntelligenceService

router = APIRouter(prefix="/monitoramento-operacional", tags=["monitoramento-operacional"])


@router.get("/runtime/health")
async def runtime_health(x_correlation_id: str | None = Header(default=None)):
    correlation_id = definir_correlation_id(x_correlation_id)
    return {
        "status": "SAUDAVEL",
        "correlation_id": correlation_id,
        "capabilities": [
            "distributed-telemetry",
            "runtime-intelligence",
            "living-observability",
            "real-resilience",
            "assisted-autonomous-operation",
        ],
    }


@router.post("/runtime/diagnostico")
async def diagnosticar_runtime(sinais: list[SinalRuntime], x_correlation_id: str | None = Header(default=None)):
    definir_correlation_id(x_correlation_id)
    diagnostico = RuntimeIntelligenceService().diagnosticar(sinais)
    acao = AutonomousOperationService().recomendar_acao(diagnostico)
    return {
        "correlation_id": obter_correlation_id(),
        "diagnostico": diagnostico.model_dump(),
        "acao_recomendada": acao,
    }
