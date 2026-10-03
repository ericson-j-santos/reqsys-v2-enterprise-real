from fastapi import APIRouter, Depends

from app.core.envelope import ok
from app.core.service_tokens import require_admin_or_service_token
from app.services.copilot_memory_install_discovery import listar_grupos_instalacao

router = APIRouter(prefix='/copilot-memory/install', tags=['Hub Low-Code & IA - Instalação Copilot Memory'])
require_install_auth = require_admin_or_service_token('copilot_memory:sincronizar')


@router.get('/groups')
async def copilot_memory_install_groups(_auth=Depends(require_install_auth)):
    return ok(await listar_grupos_instalacao())
