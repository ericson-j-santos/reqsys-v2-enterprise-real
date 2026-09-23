from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.envelope import ok
from app.core.service_tokens import require_admin_or_service_token
from app.schemas.report_builder_delivery import ReportBuilderEmailRequest
from app.services.movimento_email.sender_factory import ConfiguracaoEnvioError
from app.services.movimento_email.smtp_sender import EnvioEmailError
from app.services.report_builder_delivery import gerar_e_enviar_relatorio

router = APIRouter(prefix='/v1/report-builder', tags=['Report Builder'])

# Instância única para permitir override seguro em testes.
require_report_builder_send_auth = require_admin_or_service_token('report_builder:send')


@router.post('/reports/generate-and-email', dependencies=[Depends(require_report_builder_send_auth)])
def report_builder_generate_and_email(payload: ReportBuilderEmailRequest):
    """Gera o RDL na aplicação e envia o artefato via provedor de e-mail configurado."""
    try:
        resultado = gerar_e_enviar_relatorio(payload)
    except ConfiguracaoEnvioError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except EnvioEmailError as exc:
        raise HTTPException(status_code=502, detail=f'Falha ao enviar relatório por e-mail: {exc}') from None
    return ok(resultado, resultado['correlation_id'])
