from time import time_ns

from fastapi import APIRouter, Header, HTTPException, status

from app.core.envelope import ok
from app.schemas.processos import ContextoAntecipacao, ResultadoAntecipacao
from app.services.prontidao import antecipar_validacoes

router = APIRouter(prefix="/v1/processos", tags=["Processos"])


@router.post("/pre-validar", response_model=ResultadoAntecipacao)
def pre_validar_processo(
    contexto: ContextoAntecipacao,
    x_correlation_id: str | None = Header(default=None),
) -> ResultadoAntecipacao:
    return antecipar_validacoes(contexto)


@router.post("/iniciar")
def iniciar_processo(
    contexto: ContextoAntecipacao,
    x_correlation_id: str | None = Header(default=None),
):
    resultado = antecipar_validacoes(contexto)

    if not resultado.apto_para_iniciar:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=resultado.model_dump(),
        )

    processo_id = f"{contexto.tipo_processo.value.upper()}-{str(time_ns())[-9:]}"
    correlation = x_correlation_id or contexto.correlation_id

    return ok(
        {
            "processo_id": processo_id,
            "tipo_processo": contexto.tipo_processo.value,
            "acao": contexto.acao,
            "status": "iniciado",
            "message": "Processo iniciado com sucesso.",
            "status_validacao": resultado.status_validacao,
            "score_prontidao": resultado.score_prontidao,
            "alertas": [a.model_dump() for a in resultado.alertas],
            "correlation_id": contexto.correlation_id,
        },
        correlation,
    )
