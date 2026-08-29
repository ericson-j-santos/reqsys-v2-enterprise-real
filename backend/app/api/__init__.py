"""Bootstrap do pacote de APIs."""

import app.api.copilot_studio  # noqa: F401
import app.api.requisitos_runtime_inspection  # noqa: F401
import app.api.requisitos_runtime_transition  # noqa: F401

# Routers especializados são anexados a superfícies já incluídas pelo app.main
# para preservar os pontos canônicos de composição da aplicação.
from app.api import (  # noqa: E402
    copilot_memory,
    copilot_memory_install_discovery,
    diagram_version_governance,
    diagramas,
    gestao_ti,
    hub_lowcode,
    levantamento_requisitos,
    monitoramento_operacional,
    notificacoes,
    pentaho_integration,
    prompt_development_coordinator,
    requisitos,
    teams_gateway,
    teams_github_actions,
)

diagramas.router.include_router(diagram_version_governance.router)
hub_lowcode.router.include_router(prompt_development_coordinator.router)
hub_lowcode.router.include_router(copilot_memory.router)
hub_lowcode.router.include_router(copilot_memory_install_discovery.router)
teams_gateway.router.include_router(notificacoes.router)
teams_gateway.router.include_router(teams_github_actions.router)
requisitos.api_router.include_router(levantamento_requisitos.router)

# A camada canônica é anexada aos requisitos para preservar o app.main.
requisitos.api_router.include_router(gestao_ti.router)

# Integrações Pentaho reutilizam a superfície canônica de monitoramento sem
# introduzir um segundo ponto de composição no app.main.
monitoramento_operacional.router.include_router(pentaho_integration.router)
