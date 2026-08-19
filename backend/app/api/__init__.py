"""Bootstrap do pacote de APIs."""

import app.api.copilot_studio  # noqa: F401
import app.api.requisitos_runtime_inspection  # noqa: F401
import app.api.requisitos_runtime_transition  # noqa: F401

# O router de governanca e anexado ao router existente de diagramas para
# preservar o ponto unico de inclusao utilizado pelo app.main.
# O coordenador ADR/PDR é anexado ao Hub Low-Code para preservar o prefixo
# público existente sem duplicar include_router no app.main.
# O centro de notificações é anexado ao Teams Gateway para manter uma única
# superfície operacional de mensageria e evitar novo acoplamento no app.main.
# A coleta governada é anexada à API de requisitos para preservar o contrato
# público existente e permitir uso por ReqSys, Forms, Power Apps e Power Automate.
from app.api import (  # noqa: E402
    diagram_version_governance,
    diagramas,
    gestao_ti,
    hub_lowcode,
    levantamento_requisitos,
    notificacoes,
    prompt_development_coordinator,
    requisitos,
    teams_gateway,
)

diagramas.router.include_router(diagram_version_governance.router)
hub_lowcode.router.include_router(prompt_development_coordinator.router)
teams_gateway.router.include_router(notificacoes.router)
requisitos.api_router.include_router(levantamento_requisitos.router)

# A camada canônica é anexada aos requisitos para preservar o app.main.
requisitos.api_router.include_router(gestao_ti.router)
